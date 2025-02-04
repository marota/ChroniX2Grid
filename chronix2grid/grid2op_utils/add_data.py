# Copyright (c) 2019-2022, RTE (https://www.rte-france.com)
# See AUTHORS.txt
# This Source Code Form is subject to the terms of the Mozilla Public License, version 2.0.
# If a copy of the Mozilla Public License, version 2.0 was not distributed with this file,
# you can obtain one at http://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
# This file is part of Chronix2Grid, A python package to generate "en-masse" chronics for loads and productions (thermal, renewable)
import os
import numpy as np
import json
from multiprocessing import Pool

import grid2op
from chronix2grid.grid2op_utils.utils import generate_a_scenario, get_last_scenario_id
from numpy.random import default_rng

import pdb

def add_data(env: grid2op.Environment.Environment,
             seed=None,
             nb_scenario=1,
             nb_core=1,  # TODO
             with_loss=True):
    """This function adds some data to already existing scenarios.
    
    .. warning::
        You should not start this function twice. Before starting a new run, make sure the previous one has terminated (otherwise you might
        erase some previously generated scenario)

    Parameters
    ----------
    env : _type_
        The grid2op environment
    seed:
        The seed to use (the same seed is guaranteed to generate the same scenarios)
    nb_scenario: ``int``
        The number of scenarios to generate
    nb_core: ``int``
        The number of core you want to use (to speed up the generation process)
    with_loss: ``bool``
        Do you make sure that the generated data will not be modified too much when running with grid2op (default = True).
        Setting it to False will speed up (by quite a lot) the generation process, but will degrade the data quality.
        
    """
    # required parameters
    env_name = type(env).env_name
    output_dir = os.path.join(env.get_path_env(), "chronics")
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
        
    last_scen = get_last_scenario_id(output_dir)
    scen_ids = [f"{el}" for el in range(last_scen +1, last_scen + 1 + nb_scenario)]
    with open(os.path.join(env.get_path_env(), "scenario_params.json"), "r", encoding="utf-8") as f:
        dict_ref = json.load(f)
        
    dt = dict_ref["dt"]
    li_months = dict_ref["all_dates"]

    # generate the seeds
    if seed is not None:
        prng = default_rng(seed)
    else:
        prng = default_rng()
        
    load_seeds = []
    renew_seeds = []
    gen_p_forecast_seeds = []
    for scen_id in scen_ids:
        for start_date in li_months:
            load_seed, renew_seed, gen_p_forecast_seed = prng.integers(2**32 - 1, size=3)
            load_seeds.append(load_seed)
            renew_seeds.append(renew_seed)
            gen_p_forecast_seeds.append(gen_p_forecast_seed)
    
    # generate the data
    # TODO multi proc
    path_env = env.get_path_env()
    name_gen = env.name_gen
    gen_type = env.gen_type
    errors = {}
    argss = []
    for j, scen_id in enumerate(scen_ids):
        for i, start_date in enumerate(li_months):
            seed_num = i + j * len(li_months)
            argss.append((path_env,
                          name_gen,
                          gen_type,
                          output_dir,
                          start_date,
                          dt,
                          scen_id,
                          load_seeds[seed_num],
                          renew_seeds[seed_num],
                          gen_p_forecast_seeds[seed_num],
                          with_loss
                          ))
    if nb_core == 1:
        for args in argss:
            path_env, name_gen, gen_type, output_dir, start_date, dt, scen_id, load_seed, renew_seed, \
                gen_p_forecast_seed, handle_loss = args
            res_gen = generate_a_scenario(path_env, name_gen, gen_type, output_dir, start_date, dt, scen_id, load_seed, renew_seed, 
                                          gen_p_forecast_seed, handle_loss)
            error_, *_ = res_gen
            if error_ is not None:
                print("=============================")
                print(f"     Error for {start_date} {scen_id}        ")
                print(f"{error_}")
                print("=============================")
                errors[f'{start_date}_{scen_id}'] = f"{error_}"
                # TODO do not erase that, read it and write it if you need too
                with open(os.path.join(output_dir, "errors.json"), "w", encoding="utf-8") as f:
                    json.dump(errors, fp=f)
    else:
        with Pool(nb_core) as p:
            p.map(generate_a_scenario, argss)
