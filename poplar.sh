#!/bin/bash
#SBATCH --job-name=poplar
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH -p compute

conda activate poplar_env
python parsl/main.py ncbi_dataset/data/dataset_catalog.json -o out.tree
