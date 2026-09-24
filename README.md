# mlcast-dataset-FR-MF

This dataset contains radar data of the rainfall intensity throughout France from 2020-2024 (included). The radar recorded data every 5 minutes covering a grid of 1536 x 1536 pixels with a spatial resolution of 1 km. 
The data was originally stored in `.npz` format, which were converted into `.zarr`.


**Dataset spec.**

Radar dataset is stored in `zarr` v3 with the following shard/chunk organisation.


| Name | Shape |
|---|---|
| `"prate"` array | `(525787, 1536, 1536)` |
| `"prate"` Shard | `(288, 1536, 1536)` |
| `"prate"` Chunk | `(1, 1536, 1536)` |



## 1. Init environment

Initialise the virtual environment via [uv](https://docs.astral.sh/uv/getting-started/installation/).
```bash
uv sync
```

## 2. Download data

The data can be collected as a compressed `.tar` folder from the __Météo-France__ [dataset](https://huggingface.co/datasets/meteofrance/fr-radar-rainfall/tree/main), executing the following command:

```bash
bash scripts/download_npz.sh
```



## 3. Create an Empty Zarr Hierarchy 

Run the below command to initialise the empty structure filled with coordinates arrays and georeferencing attributes.

```bash
uv run python scripts/zarr_init.py \
    --start_date "2020-01-01 00:00:00" \
    --end_date "2024-12-31 23:59:59" \
    --delta_time 5  \
    --data_path </path/to/file.npz> \
    --pattern "202*/*.npz" \
    --output_zarr_path </path/to/output_zarr.zarr>
```


**Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `start_date` | `"2020-01-01T00:00:00"` | Start of the time range (ISO 8601) |
| `end_date` | `"2024-12-31T23:59:59"` | End of the time range (ISO 8601) |
| `delta_time` | `5` | Time interval between radar data collection (min) |
| `data_path` | *(required)* | Directory containing yearly `.npz` files |
| `pattern` | `202*/*.npz` | Glob pattern for locating `.npz` files |
| `output_zarr_path` | *(required)* | Output zarr path |

**Description:**

We initialized the structure of the `.zarr` archive by creating separate arrays to store the values corresponding to each coordinate. We stored the rain rate by creating four 1D arrays for x, y and time, two 2D array for longitude and latitude, and finally one 3D array for time, y, and x combined which represents the rainfall rate.

## 4. Storing Rainfall Rate

To store the data in the empty `prate` array, we distributed the task across multiple workers by using Python's multiprocessing library. Each worker loaded the `.npz` files, preprocessed the data to conform to CF conventions, and then stacked the 2D arrays to create a 3D array spanning 288 timestamps. The resulting array was then stored in the corresponding shard of the Zarr dataset.

Run the following command by pointing to the initialised empty zarr structure as described in #3.

```bash
uv run python scripts/zarr_converter.py \
    --zarr_path $path_to_output_zarr \
    --array_name "prate" \
    --data_path $path_to_file \
    --pattern "202*/*.npz" \
    --num_workers 4
```


**Parameters:**

| Parameter | Default | Description |
|---|---|---|
| `zarr_path` | *(required)*  | Path to pre-initialised zarr hierarchy. |
| `array_name` | `"prate"` | `zarr.Array` variable name storing precipitation |
| `data_path` | *(required)* | Directory containing yearly `.npz` files |
| `pattern` | `202*/*.npz` | Glob pattern for locating `.npz` files |
| `num_workers` | 4 | amount of parallel workers |



## 5. Patching attributes of an existing archive

The attributes of an archive that already exists (locally or on S3) can be
rewritten in place, without touching the data chunks, with:

```bash
uv run python scripts/zarr_attribute_editor.py \
    --zarr_path s3://mlcast-source-datasets/FR-MF-prate/v0.1.0/fr-mf-prate-5min.zarr \
    --profile ewc-eai-mlcast \
    --endpoint_url https://object-store.os-api.cci2.ecmwf.int \
    --created_with_version 0.1.1
```

It takes the global, `crs`, `x` and `y` attributes from the same builders used
by `zarr_init.py`, so the two scripts cannot drift apart, and re-consolidates
the metadata. Add `--dry_run` to print the attributes without writing.

**Georeferencing.** The `crs` variable carries the WKT and PROJ strings as
well as the CF grid mapping attributes (`grid_mapping_name` and the
`polar_stereographic` parameters), which are derived from the WKT with pyproj.
The `x` / `y` coordinates carry the CF `standard_name`, `units` and `axis`
attributes.

## Acknowledgements

Data provided by Météo-France. Processed and distributed by Météo-France AI Lab for open research and development purposes.

Original dataset citation:
```
@misc{radar_rainfall_france,
  title        = {5 Minutes Radar Rainfall over French Mainland Territory},
  author       = {Météo-France},
  year         = {2025},
  howpublished = {\url{https://huggingface.co/datasets/meteofrance/radar-rainfall}},
  note         = {Distributed under Etalab 2.0 License}
}
```