#!/bin/bash

output_path="./data/"

years=("2020" "2021" "2022" "2023" "2024")
for year in "${years[@]}"; do
    
    echo "Downloading $year"
    wget -O ${output_path}/${year}.tar https://huggingface.co/datasets/meteofrance/fr-radar-rainfall/resolve/main/${year}.tar?download=true

    echo "Tar extraction $year"
    tar -xvf ${output_path}/${year}.tar

    echo "Removing archive $year"
    rm ${output_path}/${year}.tar

done