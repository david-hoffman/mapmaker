#!/usr/bin/env python
# -*- coding: utf-8 -*-
# __main__.py
"""
A small utility to make maps of acquired data.

Copyright (c) 2018, David Hoffman
"""
from . import extract_locations, extract_locations_csv, load_stack, montage, calc_extent, read_montage_settings, make_fig
import glob
import warnings
import os
import click
import dask
import dask.multiprocessing
import skimage.external.tifffile as tiff


def get_locations(location_path):
    """Extract locations from given paths"""
    sim_locations = dict()
    for path in location_path:
        click.echo("Extracting cell locations from {}".format(path))
        if ".csv" in path:
            sim_locations.update(extract_locations_csv(path))
        else:
            # add a trailing / just in case
            sim_locations.update(extract_locations(os.path.join(path, "")))
    if not len(sim_locations):
        raise RuntimeError("No locations found.")
    return sim_locations

@click.command()
@click.option('--montage-dir', '-m', multiple=True, type=click.Path(exists=True, file_okay=False), help='Directory containing montage data')
@click.option('--location-path', '-l', default=list(), multiple=True, type=click.Path(exists=True), help='Top level directory containing SIM data or .csv file with locations')
@click.option('--scale', '-s', type=float, default=0.1, help='Scaling for the output images')
@click.option('--gamma', '-g', type=float, default=0.25, help='Gamma correction for the output images')
@click.option('--program-type', type=click.Choice(['VSIM', 'SPIM']), default="VSIM", help='Which program took the SIM data.')
@click.option('--tif', '-t', is_flag=True, help='Save at full bit depth')
def cli(montage_dir, location_path, scale, gamma, program_type, tif):
    """Mark imaged locations on montaged widefield data"""
    if not location_path and click.confirm('No locations indicated, do you want to continue?', default=True, abort=True):
        sim_locations = dict()
    else:
        sim_locations = get_locations(location_path)
        # print out the locations
        click.echo("Locations: ")
        click.echo("\n".join(["{} @ {:.3f}, {:.3f}".format(k, *v) for k, v in sim_locations.items()]))

    @dask.delayed
    def save_montage(montage_path):
        """Read in and save the data"""
        # add trailing slash, just to be safe
        montage_path = os.path.join(montage_path, "")
        try:
            montage_shape, tile0_loc = read_montage_settings(glob.glob(montage_path + "3D settings_*.csv")[0])
        except IndexError as e:
            click.echo("No settings file found in {}".format(montage_path))
            raise e
        click.echo("Reading data from {}".format(montage_path))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data = load_stack(montage_path)
        montage_data = montage(data, montage_shape)
        extent = calc_extent(tile0_loc, data.shape[-2:], montage_shape)
        basename = os.path.dirname(montage_path) + "_ch{}.jpg"

        for i, channel in enumerate(montage_data):
            click.echo("Saving {}".format(basename.format(i)))
            if tif:
                tiff.imsave(basename.format(i).replace(".jpg", ".tif"), channel)
            else:
                make_fig(channel, extent, sim_locations, basename.format(i),
                         scale, cmap="Greys_r", gamma=gamma)

    tocompute = dask.delayed([save_montage(montage_path) for montage_path in montage_dir])
    tocompute.compute(scheduler="processes")
        

if __name__ == '__main__':
    cli()
