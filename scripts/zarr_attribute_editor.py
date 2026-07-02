import os
import zarr
from typing import Dict
from loguru import logger
from fire import Fire

# Correct WKT 
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


def get_global_attrs():
    """
    Build the global attribures structure.
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
        "mlcast_created_with": "https://github.com/mlcast-community/mlcast-dataset-FR-MR@0.1.0",
        "mlcast_dataset_identifier": "FR-MF-prate",
        "mlcast_dataset_version": "0.1.0",
        "title": "Météo-France Radar Rainfall Archive"
    }
    return attrs


def get_georeferencing_attrs():
    """
    Build the georeferencing information attribute structure.
    """
    attrs = {  
        "proj4": PROJ4,
        "crs_wkt": PROJ_WKT_V2,
        "spatial_ref": PROJ_WKT_V2,
    }
    return attrs


def main(zarr_path: str) -> None:
    """
    Manual zarr attribute editing.
    """
    if not os.path.exists(zarr_path):
        raise NameError(f"Zarr archive {zarr_path} does not exist.")
    
    # Open zarr
    logger.info("Reading data.")
    root = zarr.open(zarr_path, mode="a")

    # Update global
    logger.info("Updating global attrs.")
    updated_global = get_global_attrs()
    root.attrs.update(updated_global)

    # Update crs
    logger.info("Updating crs attrs.")
    updated_crs = get_georeferencing_attrs()
    root["crs"].attrs.update(updated_crs)

    # Consolidate metadata
    logger.info("Consolidate metadata.")
    zarr.consolidate_metadata(zarr_path, zarr_format=3)

if __name__=="__main__":
    Fire(main)