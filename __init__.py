#!/usr/bin/env python
# -*- coding: utf-8 -*-
# __init__.py
"""
A small utility to make maps of acquired data.

Copyright (c) 2018, David Hoffman
"""
import os
import re
import glob
import textwrap
import numpy as np
import pandas as pd
import skimage.external.tifffile as tif
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm, LogNorm
from dphplotting import auto_adjust
import warnings


def load_stack(top_dir):
    """Load stack from Montage directory

    Resulting stack will be in order of channel, tile, y, x

    Note that the normal tile ordering is decreasing x then decreasing y

    But remember the scan is x then y"""
    # make container
    paths = []
    # itereate through number of channels
    for i in range(100):
        subpaths = sorted(glob.glob(top_dir + "*ch{}*.tif".format(i)))
        if not len(subpaths):
            break
        paths.append(subpaths)
    # Paths are read as a raster of left to right, top to bottom
    if not len(paths):
        raise RuntimeError("No files found in {}".format(top_dir))
    return np.asarray([[tif.imread(p) for p in subpaths] for subpaths in paths])


def read_montage_settings(path):
    """Read the montage settings from the "3D Settings*.csv" file"""
    overall_settings = pd.read_csv(path, nrows=1)
    tile_settings = pd.read_csv(path, skiprows=2, header=0).iloc[1:-2].dropna(1, "all")
    shape = tuple(overall_settings[["# Subvolume Y", "# Subvolume X"]].values.squeeze())
    # center in um
    tile0_loc = tile_settings.iloc[0][["Absolute Y (um)", "Absolute X (um)"]].values
    return shape, tile0_loc.astype(float)


def montage(stack, shape):
    """Take a stack and a new shape and cread a montage"""
    # assume data is ordered as color, tiles, ny, nx
    c, ntiles, ny, nx = stack.shape
    dy, dx = shape
    new_shape = c, dy, dx, ny, nx
    # sanity check
    assert (
        dy * dx == ntiles
    ), "Number of tiles, {}, doesn't match montage dimensions ({}, {})".format(ntiles, dy, dx)
    # reshape the stack
    reshaped_stack = stack.reshape(new_shape)
    # align the tiles
    reshaped_stack = np.rollaxis(reshaped_stack, 2, 4)
    # merge and return.
    return reshaped_stack.reshape(c, dy * ny, dx * nx)


def calc_extent(tile0_loc, tile_shape, montage_shape, pixel_size=0.13):
    """Remember that the image is oriented such that the x-axis
    is decreasing from left to right

    All units in um

    extent : scalars (left, right, bottom, top), optional, default: None
    The location, in data-coordinates, of the lower-left and
    upper-right corners. If `None`, the image is positioned such that
    the pixel centers fall on zero-based (row, column) indices.
    """
    y0, x0 = tile0_loc
    ny, nx = tile_shape
    ny_tot, nx_tot = np.multiply(tile_shape, montage_shape)
    top = y0 + (ny // 2) * pixel_size
    left = x0 + (nx // 2) * pixel_size
    bottom = top - ny_tot * pixel_size
    right = left - nx_tot * pixel_size
    return left, right, bottom, top


def clean_path(path):
    """Clean the names of the SIM images"""
    split_path = os.path.abspath(path).split(os.path.sep)
    name = split_path[-2]
    return "_".join(name.split("_")[:-2])


def extract_locations(top_level_path):
    """Extract locations from SIM data"""
    re_x = re.compile("(?<=X \(mm\) = )(-?\d+\.\d+)")
    re_y = re.compile("(?<=Y \(mm\) = )(-?\d+\.\d+)")
    d = dict()
    for path in glob.iglob(top_level_path + "/*/*config.txt"):
        path = os.path.abspath(path)
        with open(path, "r") as f:
            tmp = f.readlines()
            try:
                d[path] = (
                    set(re_y.findall("\n".join(tmp))).pop(),
                    set(re_x.findall("\n".join(tmp))).pop(),
                )
            except KeyError:
                warnings.warn("No information in {}".format(path))
                continue
    return {clean_path(k): np.asarray(v).astype(float) for k, v in d.items()}


def extract_locations_csv(csv_path):
    """Extract locations from a csv file generated by motion GUI"""
    d = pd.read_csv(csv_path)
    # clear our positions.
    # d = d[~d["Name"].str.contains("Pos")]
    return {dd["Name"]: dd[["Y (mm)", "X (mm)"]].values.astype(float) for i, dd in d.iterrows()}


def make_rec(y, x, width, height, linewidth):
    """Make a rectangle of width and height _centered_ on (y, x)"""
    return plt.Rectangle(
        (x - width / 2, y - height / 2), width, height, color="w", linewidth=linewidth, fill=False
    )


def make_fig(montage_data, extent, locations, savename, scalefactor, auto=True, **kwargs):
    """"""
    # default dpi means that each pixel is equivalent to a single printers point
    dpi = 72
    # calculate the right number of inches to have the right number of pixels
    shape = np.array(montage_data.shape)
    inches = shape / dpi * scalefactor
    # make the figure
    fig, ax = plt.subplots(figsize=inches)
    # set up default kwargs
    default_vs = {
        k: v
        for k, v in {k: kwargs.pop(k, None) for k in ("vmin", "vmax")}.items()
        if v is not None
    }
    # norm the data and auto adjust limits if requested
    normed_data = PowerNorm(kwargs.pop("gamma", 0.5), **default_vs)(montage_data)
    if auto:
        auto_vs = auto_adjust(normed_data)
    else:
        auto_vs = dict()
    kwargs.update(auto_vs)
    # do the actual plot
    ax.matshow(normed_data, extent=extent, **kwargs)
    # annotate the plot
    xmax, xmin, ymin, ymax = extent
    for title, point in locations.items():
        diameter = 512 * 0.13
        # right now y, x points are recorded in mm not um so we have to convert them.
        y, x = point * 1000
        # check if location is within range.
        if xmax >= x >= xmin and ymax >= y >= ymin:
            ax.add_patch(make_rec(y, x, diameter, diameter, max(2, 20 * scalefactor)))

            ax.annotate(
                textwrap.fill(title, 20),
                xy=(x, y),
                xycoords="data",
                bbox=dict(pad=0.3, color=(1, 1, 1, 0.5), lw=0),
                xytext=(x, y + diameter / 2 * 1.3),
                textcoords="data",
                color="k",
                horizontalalignment="center",
                verticalalignment="bottom",
                multialignment="center",
                fontsize=max(12, 120 * scalefactor),
            )
    # fix borders and such
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0, hspace=0)
    # save the fig
    bbox = matplotlib.transforms.Bbox(((0, 0), inches))
    fig.savefig(savename, dpi=dpi, bbox_inches=bbox)
