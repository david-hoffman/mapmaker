#!/usr/bin/env python
# -*- coding: utf-8 -*-
# __main__.py
"""
A small utility to make maps of acquired data.

Copyright (c) 2018, David Hoffman
"""
from . import *
import click


@click.command()
@click.option('--montage-dir', '-m', multiple=True, type=click.Path(exists=True, file_okay=False), help='Directory containing montage data')
@click.option('--location-path', '-l', multiple=True, type=click.Path(exists=True), help='Top level directory containing SIM data or .csv file with locations')
@click.option('--scale', '-s', type=float, default=0.1, help='Scaling for the output images')
@click.option('--program-type', type=click.Choice(['VSIM', 'SPIM']), default="VSIM", help='Which program took the SIM data.')
def cli(montage_dir, location_path, scale, program_type):
    """Mark imaged locations on montaged widefield data"""
    sim_locations = dict()
    for path in location_path:
        click.echo("Extracting cell locations from {}".format(path))
        if ".csv" in path:
            sim_locations.update(extract_locations_csv(path))
        else:
            sim_locations.update(extract_locations(path))
    if not len(sim_locations):
        raise RuntimeError("No locations found.")
    click.echo("Locations: ")
    click.echo("\n".join(["{} @ {:.3f}, {:.3f}".format(k, *v) for k, v in sim_locations.items()]))

    for montage_path in montage_dir:
        montage_shape, tile0_loc = read_montage_settings(glob.glob(montage_path + "3D settings_*.csv")[0])
        click.echo("Reading data from {}".format(montage_path))
        data = load_stack(montage_path)
        montage_data = montage(data, montage_shape)
        extent = calc_extent(tile0_loc, data.shape[-2:], montage_shape)
        basename = os.path.dirname(montage_path) + "_ch{}.jpg"
        for i, channel in enumerate(montage_data):
            click.echo("Saving {}".format(basename.format(i)))
            make_fig(channel, extent, sim_locations, basename.format(i),
                     scale, cmap="Greys_r", gamma=0.25)

if __name__ == '__main__':
    cli()
