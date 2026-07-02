import os
import glob
from functools import partial
import multiprocessing as mp
from multiprocessing.pool import ThreadPool as Pool
from typing import List, Tuple, Dict
from pathlib import Path
from datetime import datetime
import numpy as np
import zarr
from tqdm import tqdm
from fire import Fire


### Helper functions

def open_zarr(zarr_path: str) -> zarr.Group:
    """
    Read the empty zarr hierarchy in append mode.
    Args:
        zarr_path: (str) path to zarr folder.
    Return
        zarr.Group (the root zarr group object)
    """
    if not os.path.exists(zarr_path):
        raise NameError(f"{zarr_path} not found!")
    return zarr.open(zarr_path, mode="a")


def get_time_observed(
        data_path: str,
        pattern: str,
    ) -> List:
    """
    Get the actual time array by reading from available files in disk.
    Args:
        data_path: (str) path to files
        pattern: (str) common .npz patter
    Return
        sorted filename list
    """
    # Collect time array from source
    file_list = sorted(glob.glob(os.path.join(data_path, pattern)))
    return file_list

def collect_array_info(
        root: zarr.Group,
        array_name: str,
    ) -> Dict[str, Tuple]:
    """
    Collect the shard shape.
    Args:
        root: (zarr.Group) zarr group object mapping the root group.
        array_name: (str) zarr array name.
    """
    return{
        "shard": root[array_name].shards,
        "chunk": root[array_name].chunks,
    }

def preprocess_array(
        array: np.ndarray,
    ) -> np.ndarray:
    """
    Convert original rain amount (mm * 10^-2) into rate (mm/h).
    Args:
        array: np.ndarray
    Return:
        preprocessed array (np.ndarray)
    """
    # Filter nans
    array = np.where(array < 0, np.nan, array)

    # Convert to mm/5min
    array = array/100  

    # Convert to mm/h
    array = array*60/5

    return array

def stack_files_to_array(
        filelist: List,
        chunk_h: int,
        chunk_w: int,
        ) -> np.ndarray:
    """
    Stack multiple 2D 5min slices into a single 3D arrays.
    (To be shard-compliant)
    Args:
        filelist: (List) sorted list of filenames.
        chunk_h: (int) chunk dimension (W).
        chunk_w: (int) chunk dimension (H).
    """
    # Initialise empty structure and loop over filelist items
    stack = np.zeros((len(filelist), chunk_h, chunk_w))

    for idx , filename in enumerate(filelist):

        # Load individual array
        rain = np.load(filename)["arr_0"]

        # Do preproc
        rain = preprocess_array(rain)

        # Store in stack
        stack[idx , : , :] = rain

    return stack

def fill_shard(
        idx: int,
        filelist: List,
        root: zarr.Group,
        array_name: str,
        shard_size: int,
        chunk_h: int,
        chunk_w: int,
    ) -> bool:
    """
    Fill the current zarr empty via shard given a proper idx.
    """
    try:
        # Collect stacked array
        array = stack_files_to_array(
            filelist=filelist[idx : (idx + shard_size)],
            chunk_h=chunk_h,
            chunk_w=chunk_w,
            )
        # Store
        root[array_name][idx : (idx + shard_size)] = array

        return True
    
    except Exception as e:
        print(f"{e}\nError while processing array at idx: {idx}")
        return False



def main(
        zarr_path: str,
        array_name: str,
        data_path: str, 
        pattern: str,
        num_workers: int = 4,
    ):
    """ Description: 
    """
    # Collect filelist
    filelist = get_time_observed(data_path, pattern)

    # Open zarr
    root = open_zarr(zarr_path)

    # Collect shard info
    array_info = collect_array_info(root, array_name)
    shard_size, _, _    = array_info["shard"]
    _, chunk_h, chunk_w = array_info["chunk"]
    
    # Generate iterable idxs (starting idxs)
    iterable_idxs = list(range(0, len(filelist), shard_size)) 

    # Init partial
    fill_shard_partial = partial(
        fill_shard,
        filelist=filelist,
        root=root,
        array_name=array_name,
        shard_size=shard_size,
        chunk_h=chunk_h,
        chunk_w=chunk_w,
        )

    # while imap shows slightly better performance 
    with mp.Pool(num_workers) as pool:
        results = list(tqdm(
            pool.imap(fill_shard_partial, iterable_idxs),
            total=len(iterable_idxs),
            desc="Storing shards", 
            unit="time-shard"
        ))
        pool.close()
        pool.join()


    # # Main loop over filelist
    # for i in range(0, len(filelist), shard_size):
    #     # Filter correct start end idxs
    #     start_idx = i
    #     end_idx   = i + shard_size
    #     # Filter subset from the sorted filelist and collect stacked array
    #     array = stack_files_to_array(
    #         filelist=filelist[start_idx: end_idx],
    #         chunk_h=chunk_h,
    #         chunk_w=chunk_w,
    #     )
    #     # Saving to zarr at the corresponding idxs
    #     root[array_name][start_idx : end_idx, ...] = array


if __name__ == "__main__":

    # uv run python scripts/zarr_converter.py \
    #   --zarr_path "/data/radar/meteofrance/test_zarr_correct.zarr" \
    #   --array_name "prate" \
    #   --data_path "/data/radar/meteofrance" \
    #   --pattern "202*/*.npz" \
    #   --num_workers 4
    Fire(main)