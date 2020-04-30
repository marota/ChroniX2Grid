import os

import click

from chronix2grid import constants as cst
from chronix2grid.generation import generate_chronics as gen
from chronix2grid.generation import generation_utils as gu
from chronix2grid.kpi import main as kpis
from chronix2grid.output_processor import (
    output_processor_to_chunks, write_start_dates_for_chunks)
from chronix2grid.seed_manager import (parse_seed_arg, generate_default_seed,
                                       dump_seeds)


@click.command()
@click.option('--case', default='case118_l2rpn', help='case folder to base generation on')
@click.option('--start-date', default='2012-01-01', help='Start date to generate chronics')
@click.option('--weeks', default=4, help='Number of weeks to generate')
@click.option('--by-n-weeks', default=4, help='Size of the output chunks in weeks')
@click.option('--n_scenarios', default=1, help='Number of scenarios to generate')
@click.option('--mode', default='LRTK', help='Steps to execute : L for loads only (and KPI); R(K) for renewables (and KPI) only; LRTK for all generation')
@click.option('--input-folder',
              default=os.path.join(os.path.normpath(os.getcwd()),
                                   cst.DEFAULT_INPUT_FOLDER_NAME),
              help='Directory to read input files from.')
@click.option('--output-folder',
              default=os.path.join(os.path.normpath(os.getcwd()),
                                   cst.DEFAULT_OUTPUT_FOLDER_NAME),
              help='Directory to store output files.')
@click.option('--seed-for-loads', default=None, help='Input seed to ensure reproducibility of loads generation')
@click.option('--seed-for-res', default=None, help='Input seed to ensure reproducibility of renewables generation')
@click.option('--seed-for-dispatch', default=None, help='Input seed to ensure reproducibility of dispatch')
@click.option('--ignore-warnings', is_flag=True,
              help='Ignore the warnings related to the existence of data files '
                   'in the chosen output directory.')
def generate(case, start_date, weeks, by_n_weeks, n_scenarios, mode,
             input_folder, output_folder,
             seed_for_loads, seed_for_res, seed_for_dispatch, ignore_warnings):
    generate_inner(case, start_date, weeks, by_n_weeks, n_scenarios, mode,
                   input_folder, output_folder,
                   seed_for_loads, seed_for_res, seed_for_dispatch,
                   warn_user=not ignore_warnings)


def generate_inner(case, start_date, weeks, by_n_weeks, n_scenarios, mode,
                   input_folder, output_folder, seed_for_loads, seed_for_res,
                   seed_for_dispatch, warn_user=True):

    time_parameters = gu.time_parameters(weeks, start_date)

    generation_output_folder, kpi_output_folder = create_directory_tree(
        case, start_date, output_folder, n_scenarios, mode, warn_user=warn_user)

    generation_input_folder = os.path.join(
        input_folder, cst.GENERATION_FOLDER_NAME
    )
    kpi_input_folder = os.path.join(
        input_folder, cst.KPI_FOLDER_NAME
    )

    default_seed = generate_default_seed()
    seed_for_loads = parse_seed_arg(seed_for_loads, '--seed-for-loads',
                                    default_seed)
    seed_for_res = parse_seed_arg(seed_for_res, '--seed-for-res',
                                  default_seed)
    seed_for_dispatch = parse_seed_arg(seed_for_dispatch, '--seed-for-dispatch',
                                       default_seed)

    seeds = dict(
        loads=seed_for_loads,
        renewables=seed_for_res,
        dispatch=seed_for_dispatch
    )

    dump_seeds(generation_output_folder, seeds)

    year = time_parameters['year']

    # Chronic generation
    if 'L' in mode or 'R' in mode:
        params, loads_charac, prods_charac = gen.main(
            case, n_scenarios, generation_input_folder,
            generation_output_folder, time_parameters,
            mode, seed_for_loads, seed_for_res, seed_for_dispatch)
        if by_n_weeks is not None and 'T' in mode:
            output_processor_to_chunks(
                generation_output_folder, by_n_weeks, n_scenarios, weeks)
            write_start_dates_for_chunks(generation_output_folder, weeks,
                                         by_n_weeks, n_scenarios, start_date)

    # KPI formatting and computing
    if 'R' in mode and 'K' in mode and 'T' not in mode:
        # Get and format solar and wind on all timescale, then compute KPI and save plots
        wind_solar_only = True
        kpis.main(kpi_input_folder, generation_output_folder, kpi_output_folder,
                  year, case, n_scenarios, wind_solar_only, params,
                  loads_charac, prods_charac)

    elif 'T' in mode and 'K' in mode:
        # Get and format dispatched chronics, then compute KPI and save plots
        wind_solar_only = False
        kpis.main(kpi_input_folder, generation_output_folder, kpi_output_folder,
                  year, case, n_scenarios, wind_solar_only, params,
                  loads_charac, prods_charac)


def create_directory_tree(case, start_date, output_directory,
                          n_scenarios, mode, warn_user=True):
    gen_path_to_create = os.path.join(
        output_directory, cst.GENERATION_FOLDER_NAME, case, start_date)
    if warn_user and os.path.isdir(gen_path_to_create):
        gu.warn_if_output_folder_not_empty(gen_path_to_create)
    os.makedirs(gen_path_to_create, exist_ok=True)

    kpi_path_to_create = None
    if 'K' in mode:
        kpi_path_to_create = os.path.join(
            output_directory, cst.KPI_FOLDER_NAME, case, start_date)
        if warn_user and os.path.isdir(kpi_path_to_create):
            gu.warn_if_output_folder_not_empty(kpi_path_to_create)
        os.makedirs(kpi_path_to_create, exist_ok=True)

    scen_name_generator = gu.folder_name_pattern(
        cst.SCENARIO_FOLDER_BASE_NAME, n_scenarios)
    for i in range(n_scenarios):
        scenario_name = scen_name_generator(i)
        scenario_path_to_create = os.path.join(gen_path_to_create, scenario_name)
        os.makedirs(scenario_path_to_create, exist_ok=True)
        if 'K' in mode:
            scenario_kpi_path_to_create = os.path.join(
                kpi_path_to_create, scenario_name, cst.KPI_IMAGES_FOLDER_NAME
            )
            os.makedirs(scenario_kpi_path_to_create, exist_ok=True)

    return gen_path_to_create, kpi_path_to_create


if __name__ == "__main__":
    case = 'case118_l2rpn'
    start_date = '2012-01-01'
    weeks = 1
    by_n_weeks = 1
    n_scenarios = 1
    mode = 'LRK'
    input_folder = '/home/vrenault/Projects/ChroniX2Grid/input'
    output_folder = '/home/vrenault/Projects/ChroniX2Grid/output'
    seed = 1
    warn_user = True
    generate_inner(case, start_date, weeks, by_n_weeks, n_scenarios, mode,
                   input_folder, output_folder,
                   seed, seed, seed,
                   warn_user=warn_user)
