import os
import glob
import numpy as np
import pandas as pd
from typing import Tuple
from datetime import datetime

import zarr
from zarr.storage import LocalStore
from pyproj import CRS, Transformer

from loguru import logger
from fire import Fire

### Global variables ###

# Version of this conversion code, recorded in the ``mlcast_created_with``
# global attribute. Bump together with the git tag.
CODE_VERSION = "0.1.1"
CREATED_WITH_URL = "https://github.com/mlcast-community/mlcast-dataset-FR-MF@{version}"

# Original radar projection
PROJ_WKT_V1 = """
PROJCS["unknown",GEOGCS["unknown",DATUM["unknown",SPHEROID["unknown",6378137,298.252840776245]],
PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]]],
PROJECTION["Polar_Stereographic"],PARAMETER["latitude_of_origin",45],
PARAMETER["central_meridian",0],PARAMETER["false_easting",0],PARAMETER["false_northing",0],
UNIT["metre",1],AXIS["Easting",SOUTH],AXIS["Northing",SOUTH]]
"""

PROJ_WKT_V2 = """
PROJCS["unknown",
    GEOGCS["unknown",
        DATUM["unknown",
            SPHEROID["unknown",6378137,298.252840776245]],
        PRIMEM["Greenwich",0],
        UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]]],
    PROJECTION["Polar_Stereographic"],
    PARAMETER["latitude_of_origin",45],
    PARAMETER["central_meridian",0],
    PARAMETER["false_easting",0],
    PARAMETER["false_northing",0],
    UNIT["metre",1],
    AXIS["Easting",SOUTH],
    AXIS["Northing",SOUTH],
    USAGE[
        SCOPE["Engineering survey, topographic mapping."],
        AREA["Europe - between 39.48°N and 54.18°N; -9.96°E and 14.55°E."],
        BBOX[39.477880507122855, -9.964999999999996, 54.18403098825441, 14.54948729204824]
    ]
]
"""

# Proj conversion
PROJ4 = "+proj=stere +lat_0=90 +lat_ts=45 +lon_0=0 +x_0=0 +y_0=0 +a=6378137 +rf=298.252840776245 +units=m +no_defs +type=crs"

# Coordinate projection info
GEOTRANSFORM = (
    -619652.0953618084, # initial x0 starting point
    1000.0,             # x step (move forward by ~1000)
    -3526818.459196719, # initial y0 starting point 
    -999.9999999999997, # y step (move forward by ~1000)
)

# Array dimension
DOMAIN_DIMS = (
    1536, # Spatial domain (amount of pixel on the y axis)
    1536, # Spatial domain (amount of pixel on the x axis)
)

### Helper functions for coordinates arrays extraction ###

def get_spatial_coords_arrays(
        x0: float,
        y0: float,
        x_step: float,
        y_step: float,
        width: int,
        height: int,
        ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert a 2D array from the original projection to lat/lon coordinates.
    Args:
        x0: (float): initial x coords starting point.
        y0: (float): initial y coords starting point.
        x_step: (float): x step.
        y_step: (float): y step.
        width: (int) amount of pixels.
        height: (int) amount of pixels.
    Return:
        (x_coords, y_coords,) (1D np.ndarrays)
        (lon, lat) (2D np.ndarray)
    """
    # Init grid coords
    x_coords = x0 + np.arange(width) * x_step
    y_coords = y0 + np.arange(height) * y_step

    # Transform grid coords to lat/lon
    xx, yy = np.meshgrid(x_coords, y_coords)
    crs_src = CRS.from_wkt(PROJ_WKT_V2)
    crs_dst = CRS.from_epsg(4326)  
    to_latlon = Transformer.from_crs(crs_src, crs_dst, always_xy=True)
    lon, lat = to_latlon.transform(xx, yy)

    return x_coords, y_coords, lon, lat


def get_time_array_observed(
        data_path: str,
        pattern: str,
    ) -> np.ndarray:
    """
    Get the actual time array by reading from available files in disk.
    """
    # Collect time array from source
    file_list = sorted(glob.glob(os.path.join(data_path, pattern)))

    # Generate the corresponding datetime array
    observed_time_array = np.array(
        [
            np.datetime64(
                f"{fname[0:4]}-{fname[4:6]}-{fname[6:8]} {fname[8:10]}:{fname[10:12]}:00"
            )\
            .astype("datetime64[ns]")

            for fname in pd.Series(file_list)\
                .apply(lambda x: x.split("/")[-1].strip(".npz"))\
                .to_numpy()
        ]
    ).astype("datetime64[ns]")

    return observed_time_array
    

def get_time_array_full(
        start_date: str,
        end_date: str,
        delta_time: int
    ) -> np.ndarray:
    """
    Collect time array given the full delta_time min apart from start to end.
    Args:
        start_date: (str) initial date (format: 'YYYY-MM-DD hh:mm:ss').
        end_date: (str) final dat e(format: 'YYYY-MM-DD hh:mm:ss').
        delta_time: (int) amount of time delta (in minutes).
    Return:
        timesteps_array (np.ndarray)
    """
    return np.arange(
        np.datetime64(start_date).astype("datetime64[ns]"),
        np.datetime64(end_date).astype("datetime64[ns]"),
        np.timedelta64(delta_time, "m"),
    ).astype("datetime64[m]")


def get_missing_time_array(
        start_date: str,
        end_date: str,
        delta_time: int,
        data_path: str,
        pattern: str
    ) -> np.ndarray:
    """
    Args:
        start_date: (str) initial date (format: 'YYYY-MM-DD hh:mm:ss').
        end_date: (str) final dat e(format: 'YYYY-MM-DD hh:mm:ss').
        delta_time: (int) amount of time delta (in minutes).
        data_path: (str) path to raw data
        pattern: (str) filename pattern.
    Return:
        missing_time (np.ndarray) of the left out timesteps
    """
    # Collect expected valid time array
    observed_time_array = get_time_array_observed(data_path, pattern)
    full_time_array = get_time_array_full(start_date, end_date, delta_time)

    # Check and return missing
    missing_time = np.setdiff1d(full_time_array, observed_time_array)
    
    logger.info("Time array information:")
    print(
        f"Full theoretical date range: {full_time_array.shape[0]}\n"+\
        f"Currently saved data:        {observed_time_array.shape[0]}\n"+\
        f"Missing timesteps:           {missing_time.shape[0]}"
    )
    return missing_time


### Helper functions for attributes initialisation ###

def get_spatial_coords_attrs():
    """
    Build the spatial coordinates attributes.
    attrs must have 4 fields:
        - "y": ...
        - "x": ...
        - "lat": ...
        - "lon": ...
    """
    attrs = {
        "y": {
            "dimension_names": [
                "y"
            ],
            "standard_name": "projection_y_coordinate",
            "long_name": "y coordinate of projection",
            "units": "m",
            "axis": "Y"
        }, 
        "x": {
            "dimension_names": [
                "x"
            ],
            "standard_name": "projection_x_coordinate",
            "long_name": "x coordinate of projection",
            "units": "m",
            "axis": "X"
        }, 
        "lat": {
            "dimension_names": [
                "y",
                "x"
            ],
            "grid_mapping": "crs",
            "long_name": "Latitude",
            "standard_name": "latitude",
            "units": "degrees_north"
        }, 
        "lon": {
            "dimension_names": [
                "y",
                "x"
            ],
            "grid_mapping": "crs",
            "long_name": "Longitude",
            "standard_name": "longitude",
            "units": "degrees_east"
        }, 
    }
    return attrs

def get_time_attrs():
    """
    Build the time coordinate attributes.
    """
    attrs = {
        "dimension_names": [
            "time"
        ],
        "calendar": "proleptic_gregorian",
        "long_name": "Time",
        "standard_name": "time",
        "units": "minutes since 2020-01-01"
    }
    return attrs

def get_missing_time_attrs():
    """
    Build the missing time coordinate attributes.
    """
    attrs = {
        "dimension_names": [
            "missing_times"
        ],
        "calendar": "proleptic_gregorian",
        "units": "minutes since 2020-01-01"
    }
    return attrs

def get_georeferencing_attrs():
    """
    Build the georeferencing information attribute structure.

    Besides the WKT / PROJ strings, the grid mapping variable carries the CF
    grid mapping attributes (``grid_mapping_name`` plus the projection
    parameters, CF conventions section 5.6 and appendix F). They are derived
    from the WKT with pyproj so the two descriptions cannot drift apart.
    """
    cf_attrs = CRS.from_wkt(PROJ_WKT_V2).to_cf()
    cf_attrs.pop("crs_wkt")  # keep the hand-written WKT (with BBOX) below
    # CF requires the pole for polar_stereographic; pyproj leaves it out when
    # the projection is defined through a standard parallel.
    cf_attrs["latitude_of_projection_origin"] = 90.0
    attrs = {
        **cf_attrs,
        "proj4": PROJ4,
        "crs_wkt": PROJ_WKT_V2.strip(),
        "spatial_ref": PROJ_WKT_V2.strip(),
    }
    return attrs

#ask keven manuel
def get_rainrate_attrs():
    """
    Build the rainfall primary variable attribute structure.
    """
    attrs = {
        "dimension_names": [
            "time",
            "y",
            "x"
        ],
        "grid_mapping": "crs",
        "long_name": "Total precipitation rate",
        "standard_name": "precipitation_flux",
        "units": "kg m-2 h-1"
        }
    return attrs

def get_global_attrs(created_with_version: str = CODE_VERSION):
    """
    Build the global attributes structure.

    Args:
        created_with_version: (str) git revision of this code (tag, branch or
            commit) recorded in ``mlcast_created_with``.
    """
    attrs = {
        "Author": "Météo-France",
        "Copyright": "Météo-France",
        "Processed by": "WebValley2026, Fondazione Bruno Kessler",
        "base_frequencies": "5min:2020-01-01T00:00/2024-12-31T23:55",
        "consistent_timestep_start": "2020-01-01T00:00",
        "coordinates": "lat lon",
        "history": "Created at 2026-06-29T19:00:00+01:00",
        "license": "CC-BY-4.0", #"etalab-2.0"
        "mlcast_created_by": "WebValley2026, Fondazione Bruno Kessler, <webvalley@fbk.eu>",
        "mlcast_created_on": "2026-06-29T19:00:00+01:00",
        "mlcast_created_with": CREATED_WITH_URL.format(version=created_with_version),
        "mlcast_dataset_identifier": "FR-MF-prate",
        "mlcast_dataset_version": "0.1.0",
        "title": "Météo-France Radar Rainfall Archive"
    }
    return attrs


### Zarr initialisation ###

def initialise_empty_zarr(
        start_date: str,
        end_date: str, 
        delta_time: int,
        data_path: str,
        pattern: str,
        output_zarr_path: str,
    ) -> None:
    """
    Description:
        Initialise the zarr structure with coordinates info.
    
    Args:
        start_date: (str) initial date (format: 'YYYY-MM-DD hh:mm:ss').
        end_date: (str) final date(format: 'YYYY-MM-DD hh:mm:ss').
        delta_time: (int) amount of time delta (in minutes).
        data_path: (str) path to files in folder.
        pattern: (str) string name (example: '**/*.npz').
        output_zarr_path: (str) zarr hierarchy path.

    """
    logger.info("Collecting coordinates array.")

    # Collect coordinates arrays
    x0, x_step, y0, y_step = GEOTRANSFORM
    width, height = DOMAIN_DIMS
    x_array, y_array, lon, lat = get_spatial_coords_arrays(x0, y0, x_step, y_step, width, height)
    time_array = get_time_array_observed(data_path, pattern)
    missing_time_array = get_missing_time_array(start_date, end_date, delta_time, data_path, pattern)
    valid_time_array = time_array[~np.isin(time_array, missing_time_array)]

    # Collect attributes
    logger.info("Collecting coordinates attributes.")
    spatial_coords_attrs  = get_spatial_coords_attrs()
    time_attrs            = get_time_attrs()
    missing_time_attrs    = get_missing_time_attrs()
    georeferencing_attrs  = get_georeferencing_attrs()
    rainrate_attrs        = get_rainrate_attrs()
    global_attributes     = get_global_attrs()

    # Initialise dtype for zarr.v3 time arrays
    dtype_config = {
        "name": "numpy.datetime64",
        "configuration": {
            "unit": "m",
            "scale_factor": 1 
        }
    } 
    
    # Initialise compressor
    # Possible shuffle options (noshuffle, shuffle, bitshuffle)
    ## NOTE: Look for some possible good compressor (test shuffle)
    compressor = zarr.codecs.Zstd(level=9)

    # Initialise the hierarchy (LocalStore object)
    logger.info("Initialise zarr storage.")
    store = LocalStore(output_zarr_path)

    # Setting up the "root" group.
    root = zarr.group(store=store, zarr_format=3, overwrite=False)

    # Initialise coordinates arrays
    logger.info("Storing coordinates.")
    root.create_array(
        name="y",
        data=y_array,        
        chunks=(y_array.shape[0],),      
        compressor=compressor,
        dimension_names=["y"],
        attributes=spatial_coords_attrs["y"],  
    )

    root.create_array(
        name="x",
        data=x_array,        
        chunks=(x_array.shape[0],),      
        compressor=compressor,
        dimension_names=["x"],
        attributes=spatial_coords_attrs["x"],  
    )

    root.create_array(
        name="lat",
        data=lat,        
        chunks=lat.shape,      
        compressor=compressor,
        dimension_names=["y", "x"],
        attributes=spatial_coords_attrs["lat"],  
    )

    root.create_array(
        name="lon",
        data=lon,        
        chunks=lon.shape,       
        compressor=compressor,
        dimension_names=["y", "x"],
        attributes=spatial_coords_attrs["lon"],  
    )

    logger.info("Storing time array")
    root.create_array(
        name="time",
        data=valid_time_array,        
        chunks=(valid_time_array.shape[0],),      
        # dtype=dtype_config,
        compressor=compressor,
        dimension_names=["time"],
        attributes=time_attrs,  
    )
    logger.info("Storing missing time array")
    root.create_array(
        name="missing_times",
        data=missing_time_array,        
        chunks=(missing_time_array.shape[0],),      
        # dtype=dtype_config,
        compressor=compressor,
        dimension_names=["missing_times"],
        attributes=missing_time_attrs,  
    )

    # to be done
    root.create_array(
        name="crs",
        data=np.array(np.nan), 
        dimension_names=[],
        attributes=georeferencing_attrs,  
    )

    # Init Precipitation array
    logger.info("Initialise empty rainfall")
    root.create_array(
        name="prate",
        shape=(valid_time_array.shape[0], y_array.shape[0], x_array.shape[0],),       
        chunks=(1, y_array.shape[0], x_array.shape[0],),      
        shards=(288, y_array.shape[0], x_array.shape[0],),      
        dtype="float32",       
        fill_value=np.nan,     
        compressor=compressor,
        dimension_names=["time", "y", "x"],
        attributes=rainrate_attrs,  
    )

    # Add meta info about the zarr dataset creation (global attrs) and consolidate metadata
    logger.info("Consolidate metadata.")
    root.attrs.update(global_attributes)
    zarr.consolidate_metadata(store, zarr_format=3)
    logger.info(f"Zarr archive initialised in: {output_zarr_path}")


if __name__ == "__main__":

    # Example usage:
    # uv run python scripts/zarr_init.py \
    #   --start_date "2020-01-01 00:00:00" \
    #   --end_date "2024-12-31 23:59:59" \
    #   --delta_time 5  \
    #   --data_path "/data/radar/meteofrance" \
    #   --pattern "202*/*.npz" \
    #   --output_zarr_path "/data/radar/meteofrance/test_zarr.zarr"

    Fire(initialise_empty_zarr)    