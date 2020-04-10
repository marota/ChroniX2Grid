import os
import sys
import numpy as np
import pandas as pd


def eco2mix_to_kpi_regional(kpi_input_folder, timestep, prods_charac, loads_charac, year, params, corresp_regions):
    conso_ = pd.DataFrame()
    prod = pd.DataFrame()

    for region_fictive in corresp_regions.keys():
        region = corresp_regions[region_fictive]
        repo_in = os.path.join(kpi_input_folder, 'France/eco2mix', 'eCO2mix_RTE_'+region+'_Annuel-Definitif_'+str(year)+'.csv')

        prods_charac_ = prods_charac[prods_charac['zone']==region_fictive]
        loads_charac_ = loads_charac[loads_charac['zone'] == region_fictive]

        gens = {}
        gens['solar'] = prods_charac_[prods_charac_['type'] == 'solar']['name'].values
        gens['wind'] = prods_charac_[prods_charac_['type'] == 'wind']['name'].values
        gens['hydro'] = prods_charac_[prods_charac_['type'] == 'hydro']['name'].values
        gens['nuclear'] = prods_charac_[prods_charac_['type'] == 'nuclear']['name'].values
        gens['thermal'] = prods_charac_[prods_charac_['type'] == 'thermal']['name'].values

        corresp_carrier = {'thermal':['Gaz','Fioul','Bioénergies','Charbon'],
                           'solar':['Solaire'],
                           'wind':['Eolien'],
                           'nuclear': ['Nucléaire'],
                           'hydro':['Hydraulique']}

        # Read and rectify some strange values in eco2mix
        eco2mix = pd.read_csv(repo_in, sep = ';', encoding = 'latin1', decimal = ',')
        eco2mix = eco2mix.replace('ND', 0)
        eco2mix['Solaire'] = eco2mix['Solaire'].mask(eco2mix['Solaire'] < 0, 0)
        eco2mix = eco2mix.replace('-', 0)

        colToTake = ['Date', 'Heures', 'Consommation']
        for col in ['Fioul', 'Charbon','Gaz','Bioénergies', 'Nucléaire','Eolien', 'Solaire', 'Hydraulique']:
            if col in eco2mix.columns:
                colToTake.append(col)
                eco2mix[col] = eco2mix[col].astype(float)
        df = eco2mix[colToTake]

        # Time formatting
        df['Space'] = ' '
        df['Time'] = df['Date']+df['Space']+df['Heures']
        df['Time'] = pd.to_datetime(df['Time'], infer_datetime_format=True)
        df.set_index('Time', drop=False, inplace=True)

        # Production formatting
        for carrier_out in corresp_carrier.keys():
            agregate_carrier = np.zeros(len(df))
            for carr in corresp_carrier[carrier_out]:
                if carr in df.columns:
                    agregate_carrier += df[carr]
            df[carrier_out] = agregate_carrier

        # Equitable repartition on usecase generators
        for carrier in gens.keys():
            n = len(gens[carrier])
            for col in gens[carrier]:
                df[col] = df[carrier]/n

        # Resampling
        original_index = df.index
        df = df.resample(timestep).first()

        # Dropping useless columns
        agg_conso = df['Consommation']
        df.drop(columns=['Space', 'Date', 'Heures',
                         'Fioul', 'Charbon', 'Gaz', 'Bioénergies', 'Nucléaire', 'Eolien', 'Solaire', 'Hydraulique',
                         'Pompage', 'Consommation'] + list(corresp_carrier.keys()), inplace=True, errors='ignore')

        # Load computation
        loads = loads_charac_['name'].unique()

        # Equitable repartition on loads nodes
        conso = pd.DataFrame({'Time': df['Time']})
        for col in loads:
            conso[col] = agg_conso/len(loads)

        # Equalize timeline with synthetic
        start_date = params['start_date']
        end_date = params['end_date']
        df = df[(df.index >= start_date) & (df.index < end_date)]
        conso = conso[(conso.index>=start_date)&(conso.index<end_date)]

        # Add in dataframe
        prod = pd.concat([prod,df], axis = 1)
        conso_ = pd.concat([conso_, conso], axis=1)

    # Read price data if exists
    repo_in = os.path.join(kpi_input_folder, 'France/eco2mix/price_'+str(year)+'.csv')
    try:
        price = pd.read_csv(repo_in, sep=';', decimal='.')
        price.index = original_index[original_index.notnull()]
        price = price.resample(timestep).first()
        price = price[(price.index >= start_date) & (price.index < end_date)]
    except:
        price = None
    return prod, conso_, price

def eco2mix_to_kpi(kpi_input_folder, timestep, prods_charac, loads_charac, year, params):
    repo_in = os.path.join(kpi_input_folder, 'eco2mix', 'eCO2mix_RTE_Annuel-Definitif_'+str(year)+'.csv')

    gens = {}
    gens['solar'] = prods_charac[prods_charac['type'] == 'solar']['name'].values
    gens['wind'] = prods_charac[prods_charac['type'] == 'wind']['name'].values
    gens['hydro'] = prods_charac[prods_charac['type'] == 'hydro']['name'].values
    gens['nuclear'] = prods_charac[prods_charac['type'] == 'nuclear']['name'].values
    gens['thermal'] = prods_charac[prods_charac['type'] == 'thermal']['name'].values

    corresp_carrier = {'thermal':['Gaz','Fioul','Bioénergies','Charbon'],
                       'solar':['Solaire'],
                       'wind':['Eolien'],
                       'nuclear': ['Nucléaire'],
                       'hydro':['Hydraulique','Pompage']}

    eco2mix = pd.read_csv(repo_in, sep = ';', encoding = 'latin1', decimal = ',')
    df = eco2mix[['Date', 'Heures', 'Fioul', 'Charbon','Gaz','Bioénergies', 'Nucléaire','Eolien', 'Solaire', 'Hydraulique','Pompage']]

    # Time formatting
    df['Space'] = ' '
    df['Time'] = df['Date']+df['Space']+df['Heures']
    df['Time'] = pd.to_datetime(df['Time'], infer_datetime_format=True)
    df.set_index('Time', drop=False, inplace=True)

    # Production formatting
    for carrier_out in corresp_carrier.keys():
        df[carrier_out] = df[corresp_carrier[carrier_out]].sum(axis = 1)

    # # Temporary
    # tmp = df[['solar']].copy()
    # tmp = tmp.resample('1H').first()
    # array = tmp['solar'].to_numpy()
    # print(tmp)
    # print(array)
    # file = open(r'D:\RTE\Challenge\1 - Développement\ChroniX2Grid\chronix2grid\generation\input_Nico\solar_pattern.npy', 'wb')
    # tmp.save(file, array)

    # Equitable repartition on usecase generators
    for carrier in gens.keys():
        n = len(gens[carrier])
        for col in gens[carrier]:
            df[col] = df[carrier]/n

    df.drop(columns=['Space', 'Date', 'Heures',
                     'Fioul', 'Charbon', 'Gaz', 'Bioénergies', 'Nucléaire', 'Eolien', 'Solaire', 'Hydraulique',
                     'Pompage']+list(corresp_carrier.keys()), inplace=True)

    # Resampling
    df = df.resample(timestep).first()

    # Load computation
    loads = loads_charac['name'].unique()
    agg_conso = df.sum(axis = 1).values

    # Equitable repartition on loads nodes
    conso = pd.DataFrame({'Time': df['Time']})
    for col in loads:
        conso[col] = agg_conso/len(loads)

    # Equalize timeline with synthetic
    start_date = params['start_date']
    end_date = params['end_date']
    df = df[(df.index >= start_date) & (df.index < end_date)]
    conso = conso[(conso.index>=start_date)&(conso.index<end_date)]

    return df, conso

def renewableninja_to_kpi(kpi_input_folder, timestep, loads_charac, prods_charac, year, params, corresp_regions):
    print("Importing and formatting data downloaded from Renewable Ninja API")
    repo_in_solar = os.path.join(kpi_input_folder, 'France/renewable_ninja', 'solar_case118_' + str(year) + '.csv')
    ninja_solar = pd.read_csv(repo_in_solar, sep=';', encoding='latin1', decimal='.')
    repo_in_wind = os.path.join(kpi_input_folder, 'France/renewable_ninja', 'wind_case118_' + str(year) + '.csv')
    ninja_wind = pd.read_csv(repo_in_wind, sep=';', encoding='latin1', decimal='.')
    timestep_ninja = 60 # Pas de temps une heure dans l'extraction renewable ninja
    ninja = pd.concat([ninja_solar, ninja_wind], axis = 1)

    # Time column to add !
    start_date = pd.to_datetime(str(year)+'-01-01')
    end_date = pd.to_datetime(str(year+1) + '-01-01')
    datetime_index = pd.date_range(
        start=start_date,
        end=end_date,
        freq=str(timestep_ninja) + 'min')
    datetime_index = datetime_index[:len(datetime_index)-1]

    # Resample
    ninja.index = datetime_index
    if int(timestep[:2]) < 60:
        print('Erreur: Renewable ninja requires timestep >60 min to compute KPI. Please change timestep in paramsKPI.json')
        sys.exit()
    ninja = ninja.resample(timestep).first()
    ninja['Time'] = ninja.index

    # Columns of zeros for non wind and solar generators
    gens= prods_charac[~(prods_charac['type'].isin(['solar','wind']))]['name'].values
    for gen in gens:
        ninja[gen] = 0.

    ## Load from regional eco2mix
    conso_ = pd.DataFrame()

    for region_fictive in corresp_regions.keys():
        region = corresp_regions[region_fictive]
        repo_in = os.path.join(kpi_input_folder, 'France/eco2mix',
                               'eCO2mix_RTE_' + region + '_Annuel-Definitif_' + str(year) + '.csv')

        loads_charac_ = loads_charac[loads_charac['zone'] == region_fictive]

        eco2mix = pd.read_csv(repo_in, sep=';', encoding='latin1', decimal=',')
        colToTake = ['Date', 'Heures', 'Consommation']
        df = eco2mix[colToTake]

        # Time formatting
        df['Space'] = ' '
        df['Time'] = df['Date'] + df['Space'] + df['Heures']
        df['Time'] = pd.to_datetime(df['Time'], infer_datetime_format=True)
        df.set_index('Time', drop=False, inplace=True)
        df = df.replace('-', 0)
        df = df.replace('ND', 0)


        # Resampling
        df = df.resample(timestep).first()
        agg_conso = df['Consommation'].astype(float)

        # Load computation
        loads = loads_charac_['name'].unique()

        # Equitable repartition on loads nodes
        conso = pd.DataFrame({'Time': df['Time']})
        for col in loads:
            conso[col] = agg_conso / len(loads)

        conso_ = pd.concat([conso_, conso], axis = 1)

    # Equalize timeline with synthetic
    start_date = params['start_date']
    end_date = params['end_date']
    ninja = ninja[(ninja.index >= start_date) & (ninja.index < end_date)]
    conso_ = conso_[(conso_.index >= start_date) & (conso_.index < end_date)]

    return ninja, conso_

def chronics_to_kpi(year, n_scenario, repo_in, timestep, params, thermal = True, monthly = False):

    print(" Formatting chronics for KPI")

    if thermal:

        if monthly:
            price = pd.DataFrame()
            prod_p = pd.DataFrame()
            load_p = pd.DataFrame()

            for month in range(1, 13):
                print('Month number ' + str(month))

                folder = os.path.join(repo_in, str(year), 'Scenario_'+str(n_scenario), str(year)+'_'+str(month))
                prod_p_ = pd.read_csv(os.path.join(folder,'prod_p.csv.bz2'), sep = ';', decimal = '.')
                load_p_ = pd.read_csv(os.path.join(folder,'load_p.csv.bz2'), sep = ';', decimal = '.')
                price_ = pd.read_csv(os.path.join(folder,'price.csv'), sep = ';', decimal = '.')

                for df in load_p_, prod_p_:
                    df.rename(columns = {'datetime':'Time'}, inplace = True)

                prod_p = prod_p.append(prod_p_)
                load_p = load_p.append(load_p_)
                price = price.append(price_)
            price['Time'] = load_p['Time']

        else:
            print('Year ' + str(year))
            folder = os.path.join(repo_in, str(year), 'Scenario_' + str(n_scenario), 'chronics')
            prod_p = pd.read_csv(os.path.join(folder, 'prod_p.csv.bz2'), sep=';', decimal='.')
            load_p = pd.read_csv(os.path.join(folder, 'load_p.csv.bz2'), sep=';', decimal='.')
            price = pd.read_csv(os.path.join(folder, 'prices.csv.bz2'), sep=';', decimal='.')

            # Rebuild of timeline
            datetime_index = pd.date_range(
                start=params['start_date'],
                end=params['end_date'],
                freq=str(params['dt']) + 'min')

            prod_p['Time'] = datetime_index[:len(prod_p)]
            load_p['Time'] = datetime_index[:len(load_p)]
            price['Time'] = datetime_index[:len(price)]
            #load_p.rename(columns={'datetime': 'Time'}, inplace=True)

    else:
        print('Year '+str(year))
        folder = os.path.join(repo_in, 'dispatch', str(year), 'Scenario_' + str(n_scenario))
        solar_p = pd.read_csv(os.path.join(folder, 'solar_p.csv.bz2'), sep=';', decimal='.')

        wind_p = pd.read_csv(os.path.join(folder, 'wind_p.csv.bz2'), sep=';', decimal='.')
        wind_p.drop(columns = ['datetime'],inplace = True)


        load_p = pd.read_csv(os.path.join(folder, 'load_p.csv.bz2'), sep=';', decimal='.')

        prod_p = pd.concat([solar_p, wind_p], axis=1)

        for df in load_p, prod_p:
            df.rename(columns={'datetime': 'Time'}, inplace=True)

    # Optional resampling
    load_p['Time'] = pd.to_datetime(load_p['Time'])
    load_p.set_index('Time', drop=False, inplace=True)
    load_p = load_p.resample(timestep).first()

    prod_p['Time'] = pd.to_datetime(prod_p['Time'])
    prod_p.set_index('Time', drop=False, inplace=True)
    prod_p = prod_p.resample(timestep).first()

    if not thermal:
        return prod_p, load_p
    if thermal:
        price['Time'] = pd.to_datetime(price['Time'])
        price.set_index('Time', drop=True, inplace=True)
        price = price.resample(timestep).first()
        return prod_p, load_p, price

