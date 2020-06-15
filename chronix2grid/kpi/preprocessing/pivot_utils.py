import os
import sys
import numpy as np
import pandas as pd

import chronix2grid.constants as cst


def eco2mix_to_kpi_regional(kpi_input_folder, timestep, prods_charac, loads_charac, year, params, corresp_regions):
    # Initialize dataframes to fill
    print("Importing and formatting data downloaded from regional eco2mix data")
    conso_ = pd.DataFrame()
    prod = pd.DataFrame()

    # Read data per region in corresp_regions
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

        # Read and correct some strange values in eco2mix
        eco2mix = pd.read_csv(repo_in, sep = ';', encoding = 'latin1', decimal = ',')
        eco2mix = eco2mix.replace('ND', 0)
        eco2mix['Solaire'] = eco2mix['Solaire'].mask(eco2mix['Solaire'] < 0, 0)
        eco2mix = eco2mix.replace('-', 0)

        # Format columns names and types
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

        # Equitable repartition among region generators
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

        # Equalize timeline with synthetic chronics
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


def renewableninja_to_kpi(kpi_input_folder, timestep, loads_charac,
                          prods_charac, year, params, corresp_regions, case):

    # Initialize data frame for production
    print("Importing and formatting data downloaded from Renewable Ninja API")
    solar_file_name = f'solar.csv'
    wind_file_name = f'wind.csv'
    repo_in_solar = os.path.join(
        kpi_input_folder, cst.REFERENCE_ZONE,
        cst.RENEWABLE_NINJA_REFERENCE_FOLDER, case, solar_file_name)
    ninja_solar = pd.read_csv(repo_in_solar, sep=';', encoding='latin1', decimal='.')
    repo_in_wind = os.path.join(
        kpi_input_folder, cst.REFERENCE_ZONE,
        cst.RENEWABLE_NINJA_REFERENCE_FOLDER, case, wind_file_name)
    ninja_wind = pd.read_csv(repo_in_wind, sep=';', encoding='latin1', decimal='.')
    timestep_ninja = 60 # Pas de temps une heure dans l'extraction renewable ninja
    ninja = pd.concat([ninja_solar, ninja_wind], axis = 1)

    # Time column to add
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

    ## Electricty consumption from regional eco2mix
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

        # Correct some strange values in eco2mix data
        df = df.replace('-', 0)
        df = df.replace('ND', 0)


        # Resampling
        df = df.resample(timestep).first()
        agg_conso = df['Consommation'].astype(float)

        # Equitable repartition on loads nodes
        loads = loads_charac_['name'].unique()
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


def chronics_to_kpi(chronics_repo, timestep, params, thermal = True):

    print("Importing and formatting synthetic chronics")

    if thermal:
        ## Format when all dispatch is generated

        # Read generated chronics after dispatch phase
        prod_p = pd.read_csv(os.path.join(chronics_repo, 'prod_p.csv.bz2'),
                             sep=';', decimal='.')
        load_p = pd.read_csv(os.path.join(chronics_repo, 'load_p.csv.bz2'),
                             sep=';', decimal='.')
        price = pd.read_csv(os.path.join(chronics_repo, 'prices.csv.bz2'),
                            sep=';', decimal='.')

        # Rebuild timeline
        datetime_index = pd.date_range(
            start=params['start_date'],
            end=params['end_date'],
            freq=str(params['dt']) + 'min')

        prod_p['Time'] = datetime_index[:len(prod_p)]
        load_p['Time'] = datetime_index[:len(load_p)]
        price['Time'] = datetime_index[:len(price)]

    else:
        ## Format synthetic chronics when no dispatch has been done
        solar_p = pd.read_csv(os.path.join(chronics_repo, 'solar_p.csv.bz2'), sep=';', decimal='.')
        wind_p = pd.read_csv(os.path.join(chronics_repo, 'wind_p.csv.bz2'), sep=';', decimal='.')
        wind_p.drop(columns = ['datetime'],inplace = True)
        prod_p = pd.concat([solar_p, wind_p], axis=1)

        load_p = pd.read_csv(os.path.join(chronics_repo, 'load_p.csv.bz2'), sep=';', decimal='.')

        # Timeline has already been written
        for df in load_p, prod_p:
            df.rename(columns={'datetime': 'Time'}, inplace=True)

    # Optional resampling
    load_p['Time'] = pd.to_datetime(load_p['Time'])
    load_p.set_index('Time', drop=False, inplace=True)
    load_p = load_p.resample(timestep).first()

    prod_p['Time'] = pd.to_datetime(prod_p['Time'])
    prod_p.set_index('Time', drop=False, inplace=True)
    prod_p = prod_p.resample(timestep).first()

    ## Return with price if dispatch has been made
    if not thermal:
        return prod_p, load_p
    if thermal:
        price['Time'] = pd.to_datetime(price['Time'])
        price.set_index('Time', drop=True, inplace=True)
        price = price.resample(timestep).first()
        return prod_p, load_p, price


def nrel_to_kpi(kpi_input_folder, timestep, prods_charac, loads_charac, params, year):

    # Read relation between reference generators and regions
    corresp_regions_gens = pd.read_csv(os.path.join(kpi_input_folder, 'Texas', 'corresp_gens.csv'), sep = ';')
    corresp_regions_loads = pd.read_csv(os.path.join(kpi_input_folder, 'Texas', 'corresp_loads.csv'), sep = ';')

    # Initialize data frame for production
    print("Importing and formatting data downloaded from NREL Texas")
    repo_in_prod = os.path.join(kpi_input_folder, 'Texas', 'prod_2007.csv.bz2')
    nrel_prod = pd.read_csv(repo_in_prod, sep=',', encoding='latin1', decimal='.')

    repo_in_load = os.path.join(kpi_input_folder, 'Texas', 'load_2007.csv.bz2')
    nrel_load = pd.read_csv(repo_in_load, sep=',', encoding='latin1', decimal='.')

    # Datetime processing
    nrel_prod['datetime'] = pd.to_datetime(nrel_prod['datetime'])
    nrel_load['datetime'] = pd.to_datetime(nrel_load['datetime'])

    # Test if chosen timestep is relevant for NREL
    timestep_int = int(timestep[:2])
    if timestep_int < 5:
        print('Erreur: NREL requires timestep >15 min to compute KPI. Please change timestep in paramsKPI.json')
        sys.exit()

    # For each fictive region, rearange generators and load nodes to get as many as in synthetic configuration
    ref_prod = pd.DataFrame({'datetime':nrel_prod['datetime']})
    ref_load = pd.DataFrame({'datetime':nrel_prod['datetime']})

    regions = corresp_regions_gens['zone'].unique()
    for region_fictive in regions:
        ref_prod_ = pd.DataFrame({'datetime':nrel_prod.index})
        ref_load_ = pd.DataFrame({'datetime':nrel_load.index})

        # Production generators
        ref_gens = corresp_regions_gens[corresp_regions_gens['zone']==region_fictive]['name'].unique()
        nref = len(ref_gens)
        syn_gens = prods_charac[prods_charac['zone'] == region_fictive]['name'].unique()
        nsyn = len(syn_gens)


        if nref <= nsyn:
            for i, col in enumerate(syn_gens):
                if i < (nref-1):
                    ref_prod_[col] = nrel_prod[ref_gens[i]].astype(float)
                else:
                    ref_prod_[col] = nrel_prod[ref_gens[(nref-1)]].astype(float)/(nsyn-nref+1)
        else:
            for i, col in enumerate(syn_gens):
                if i < (nsyn-1):
                    ref_prod_[col] = nrel_prod[ref_gens[i]].astype(float)
                else:
                    ref_prod_[col] = nrel_prod[ref_gens[i:len(ref_gens)]].sum(axis = 1)
        ref_prod_.drop(columns = ['datetime'], inplace=True)
        ref_prod = pd.concat([ref_prod, ref_prod_], axis=1)

        # Loads nodes with same principle
        ref_gens = corresp_regions_loads[corresp_regions_loads['zone']==region_fictive]['name'].unique()
        nref = len(ref_gens)
        syn_gens = loads_charac[loads_charac['zone'] == region_fictive]['name'].unique()
        nsyn = len(syn_gens)

        if nref <= nsyn:
            for i, col in enumerate(syn_gens):
                if i < (nref-1):
                    ref_load_[col] = nrel_load[ref_gens[i]].astype(float)
                else:
                    ref_load_[col] = nrel_load[ref_gens[(nref-1)]].astype(float)/(nsyn-nref+1)
        else:
            for i, col in enumerate(syn_gens):
                if i < (nsyn - 1):
                    ref_load_[col] = nrel_load[ref_gens[i]].astype(float)
                else:
                    ref_load_[col] = nrel_load[ref_gens[i:len(ref_gens)]].sum(axis=1).astype(float)
        ref_load_.drop(columns=['datetime'], inplace = True)
        ref_load = pd.concat([ref_load, ref_load_], axis = 1)

    # Set datetime limits and resample like synthetic chronics
    ref_prod.set_index('datetime', inplace = True)
    ref_load.set_index('datetime', inplace=True)
    ref_prod = ref_prod.resample(timestep).first()
    ref_load = ref_load.resample(timestep).first()

    start_date = params['start_date']
    end_date = params['end_date']
    ref_prod.index = [ts.replace(year = year) for ts in ref_prod.index]
    ref_load.index = [ts.replace(year=year) for ts in ref_load.index]
    ref_prod = ref_prod[(ref_prod.index >= start_date) & (ref_prod.index < end_date)]
    ref_load = ref_load[(ref_load.index >= start_date) & (ref_load.index < end_date)]

    return ref_prod, ref_load