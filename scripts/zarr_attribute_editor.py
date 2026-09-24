"""
Patch the attributes of an existing FR-MF zarr archive in place.

Rewrites the global, ``crs``, ``x`` and ``y`` attributes from the builders in
``zarr_init`` (the single source of truth) and re-consolidates the metadata.
Data chunks are never touched, so this is cheap to run on the published
archive on S3 as well as on a local copy.

Example (local):
    uv run python scripts/zarr_attribute_editor.py --zarr_path /data/fr-mf-prate-5min.zarr

Example (S3, credentials from an AWS profile):
    uv run python scripts/zarr_attribute_editor.py \\
        --zarr_path s3://mlcast-source-datasets/FR-MF-prate/v0.1.0/fr-mf-prate-5min.zarr \\
        --profile ewc-eai-mlcast \\
        --endpoint_url https://object-store.os-api.cci2.ecmwf.int \\
        --created_with_version 0.1.1
"""

import json
import os

import zarr
from zarr.storage import FsspecStore, LocalStore
from loguru import logger
from fire import Fire

from zarr_init import (
    CODE_VERSION,
    get_georeferencing_attrs,
    get_global_attrs,
    get_spatial_coords_attrs,
)


def open_store(zarr_path: str, profile: str | None, endpoint_url: str | None):
    """
    Open a local path or an ``s3://`` URL as a writable zarr store.
    """
    if zarr_path.startswith("s3://"):
        storage_options = {}
        if profile:
            storage_options["profile"] = profile
        if endpoint_url:
            storage_options["endpoint_url"] = endpoint_url
        return FsspecStore.from_url(zarr_path.rstrip("/"), storage_options=storage_options)
    if not os.path.exists(zarr_path):
        raise NameError(f"Zarr archive {zarr_path} does not exist.")
    return LocalStore(zarr_path)


def main(
        zarr_path: str,
        profile: str | None = None,
        endpoint_url: str | None = None,
        created_with_version: str = CODE_VERSION,
        dry_run: bool = False,
    ) -> None:
    """
    Update the attributes of an existing zarr archive and re-consolidate.

    Args:
        zarr_path: (str) local path or ``s3://bucket/path.zarr`` URL.
        profile: (str) AWS profile name providing the S3 credentials.
        endpoint_url: (str) S3 endpoint URL (e.g. the EWC object store).
        created_with_version: (str) git revision (tag, branch or commit) of
            this code, recorded in ``mlcast_created_with``.
        dry_run: (bool) only print the attributes that would be written.
    """
    updates = {
        "": get_global_attrs(created_with_version),
        "crs": get_georeferencing_attrs(),
        "x": get_spatial_coords_attrs()["x"],
        "y": get_spatial_coords_attrs()["y"],
    }
    if dry_run:
        logger.info("Dry run, attributes that would be written:")
        print(json.dumps(updates, indent=2, ensure_ascii=False))
        return

    logger.info(f"Opening {zarr_path}")
    store = open_store(zarr_path, profile, endpoint_url)
    root = zarr.open_group(store, mode="r+", use_consolidated=False)

    for name, attrs in updates.items():
        node = root if name == "" else root[name]
        logger.info(f"Updating attrs of {name or 'root'} ({len(attrs)} keys)")
        node.attrs.update(attrs)

    logger.info("Consolidating metadata.")
    zarr.consolidate_metadata(store, zarr_format=3)
    logger.info("Done.")


if __name__ == "__main__":
    Fire(main)
