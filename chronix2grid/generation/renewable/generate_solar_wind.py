# Copyright (c) 2019-2022, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of Chronix2Grid, A python package to generate "en-masse" chronics for loads and productions (thermal, renewable)

import os
import json

# Other Python libraries
import pandas as pd
import numpy as np
from numpy.random import default_rng

# Libraries developed for this module
from . import solar_wind_utils as swutils
from .. import generation_utils as utils
import chronix2grid.constants as cst


def main(scenario_destination_path, seed, params, prods_charac, solar_pattern, write_results = True):
    """
    This is the solar and wind production generation function, it allows you to generate consumption chronics based on
    production nodes characteristics and on a solar typical yearly production patterns.

    Parameters
    ----------
    scenario_destination_path (str): Path of output directory
    seed (int): random seed of the scenario
    params (dict): system params such as timestep or mesh characteristics
    prods_charac (pandas.DataFrame): characteristics of production nodes such as Pmax and type of production
    solar_pattern (pandas.DataFrame): hourly solar production pattern for a year. It represent specificity of the production region considered
    smoothdist (float): parameter for smoothing
    write_results (boolean): whether to write results or not. Default is True

    Returns
    -------
    pandas.DataFrame: solar production chronics generated at every node with additional gaussian noise
    pandas.DataFrame: solar production chronics forecasted for the scenario without additional gaussian noise
    pandas.DataFrame: wind production chronics generated at every node with additional gaussian noise
    pandas.DataFrame: wind production chronics forecasted for the scenario without additional gaussian noise
    """

    prng = default_rng(seed)
    smoothdist = params['smoothdist']

    # Define datetime indices
    datetime_index = pd.date_range(
        start=params['start_date'],
        end=params['end_date'],
        freq=str(params['dt']) + 'min')

    # Solar_pattern management
    # Extra value (resolution 1H, 8761)
    solar_pattern = solar_pattern[:-1]

    # Realistic first day of year: have to roll the pattern to fit first day of week
    # start_date = params['start_date']
    # start_date_day = start_date.weekday()
    # pattern_start_date = pd.Timestamp("01-01-"+str(int(params['year_solar_pattern'])))
    # pattern_start_date_day = pattern_start_date.weekday()
    # days_to_shift = start_date_day - pattern_start_date_day
    # steps_to_shift = int(days_to_shift * 60 * 24 / params['dt']) # Solar pattern starts on a monday at 0h + timestep
    # solar_pattern = np.roll(solar_pattern, steps_to_shift)

    # Generate GLOBAL temperature noise
    print('Computing global auto-correlated spatio-temporal noise for sun and wind...')
    scale_solar_coord_for_correlation = float(params["scale_solar_coord_for_correlation"]) if "scale_solar_coord_for_correlation" in params else None
    add_dim = 0
    dx_corr = int(params['dx_corr'])
    dy_corr = int(params['dy_corr'])
    for x, y, type_gen  in zip(prods_charac["x"], prods_charac["y"], prods_charac["type"]):
        if type_gen == "solar" and scale_solar_coord_for_correlation is not None:
            x = scale_solar_coord_for_correlation * x
            y = scale_solar_coord_for_correlation * y
        x_plus = int(x // dx_corr + 1)
        y_plus = int(y // dy_corr + 1)
        add_dim = max(y_plus, add_dim)
        add_dim = max(x_plus, add_dim)
    solar_noise = utils.generate_coarse_noise(prng, params, 'solar', add_dim=add_dim)
    long_scale_wind_noise = utils.generate_coarse_noise(prng, params, 'long_wind', add_dim=add_dim)
    medium_scale_wind_noise = utils.generate_coarse_noise(prng, params, 'medium_wind', add_dim=add_dim)
    short_scale_wind_noise = utils.generate_coarse_noise(prng, params, 'short_wind', add_dim=add_dim)

    # Compute Wind and solar series of scenario
    print('Generating solar and wind production chronics')
    prods_series = {}
    for name in prods_charac['name']:
        mask = (prods_charac['name'] == name)
        if prods_charac[mask]['type'].values == 'solar':
            locations = [prods_charac[mask]['x'].values[0], prods_charac[mask]['y'].values[0]]
            Pmax = prods_charac[mask]['Pmax'].values[0]
            prods_series[name] = swutils.compute_solar_series(
                prng,
                locations,
                Pmax,
                solar_noise,
                params, solar_pattern, smoothdist,
                time_scale=params['solar_corr'],
                add_dim=add_dim,
                scale_solar_coord_for_correlation=scale_solar_coord_for_correlation)

        elif prods_charac[mask]['type'].values == 'wind':
            locations = [prods_charac[mask]['x'].values[0], prods_charac[mask]['y'].values[0]]
            Pmax = prods_charac[mask]['Pmax'].values[0]
            prods_series[name] = swutils.compute_wind_series(
                prng,
                locations,
                Pmax,
                long_scale_wind_noise,
                medium_scale_wind_noise,
                short_scale_wind_noise,
                params, smoothdist,
                add_dim=add_dim)

    # Séparation ds séries solaires et éoliennes
    solar_series = {}
    wind_series = {}
    for name in prods_charac['name']:
        mask = (prods_charac['name'] == name)
        if prods_charac[mask]['type'].values == 'solar':
            solar_series[name] = prods_series[name]
        elif prods_charac[mask]['type'].values == 'wind':
            wind_series[name] = prods_series[name]

    # Time index
    prods_series['datetime'] = datetime_index
    solar_series['datetime'] = datetime_index
    wind_series['datetime'] = datetime_index

    # Save files
    if scenario_destination_path is not None:
        print('Saving files in zipped csv')
        if not os.path.exists(scenario_destination_path):
            os.makedirs(scenario_destination_path)
            
    prod_solar_forecasted =  swutils.create_csv(
        prng,
        solar_series,
        os.path.join(scenario_destination_path, 'solar_p_forecasted.csv.bz2') if scenario_destination_path is not None else None,
        reordering=True,
        shift=True,
        write_results=write_results,
        index=False
    )

    prod_solar = swutils.create_csv(
        prng,
        solar_series,
        os.path.join(scenario_destination_path, 'solar_p.csv.bz2') if scenario_destination_path is not None else None,
        reordering=True,
        noise=params['planned_std'],
        write_results=write_results
    )

    prod_wind_forecasted = swutils.create_csv(
        prng,
        wind_series,
        os.path.join(scenario_destination_path, 'wind_p_forecasted.csv.bz2') if scenario_destination_path is not None else None,
        reordering=True,
        shift=True,
        write_results=write_results,
        index=False
    )

    prod_wind = swutils.create_csv(
        prng,
        wind_series, os.path.join(scenario_destination_path, 'wind_p.csv.bz2') if scenario_destination_path is not None else None,
        reordering=True,
        noise=params['planned_std'],
        write_results=write_results
    )

    prod_p = swutils.create_csv(
        prng,
        prods_series, os.path.join(scenario_destination_path, 'prod_p.csv.bz2') if scenario_destination_path is not None else None,
        reordering=True,
        noise=params['planned_std'],
        write_results=write_results
    )

    prod_v = prods_charac[['name', 'V']].set_index('name')
    prod_v = prod_v.T
    prod_v.index = [0]
    prod_v = prod_v.reindex(range(len(prod_p)))
    prod_v = prod_v.fillna(method='ffill') * 1.04
    
    if write_results:
        prod_v.to_csv(
            os.path.join(scenario_destination_path, 'prod_v.csv.bz2') if scenario_destination_path is not None else None,
            sep=';',
            index=False,
            float_format=cst.FLOATING_POINT_PRECISION_FORMAT
        )

    return prod_solar, prod_solar_forecasted, prod_wind, prod_wind_forecasted