# Poplar

## Features

Poplar is a software pipeline that uses an input of genes and assembled genomes and generates a phylogenetic tree from the input. It connects tools to identify genes within assembled genomes, group sequences to construct gene trees, and then infer a species tree based on the gene trees.

## Quickstart

The script `setup.sh` installs the required dependencies. This requires `conda` to be already installed, and will create a conda environment `poplar_env`. It will also autopopulate `parsl/config.py` with the path to the dependencies.

In order to configure Parsl, the parallelism manager, view `parsl/config.py` and check the `SlurmProvider` information. The partition name will be machine specific, so must be selected by the user. Default options are included for `walltime`, the maximum time for a Parsl block, and `nodes_per_block`, `init_blocks`, and `max_blocks`, traits of [Parsl blocks](https://parsl.readthedocs.io/en/stable/userguide/execution.html), and should be reviewed before running a job.

Sample Pleurotus data can be downloaded by running `datasets download genome taxon  5320 --include genome,gff3,cds && unzip ncbi_dataset.zip`

Finally, run `python parsl/main.py ncbi_dataset/data/dataset_catalog.json out.tree` or update the partition name in `parsl.sh` and submit to Slurm.

## Installation and Dependencies

Poplar brings together a collection of other tools and is designed to simplify the path from genome/gene data to species tree. This does mean that there are a large number of dependencies, and a configuration file that needs to be updated for the particular machine.

The recommended process for Linux installation is running `setup.sh`, which requires conda. This will create a conda environment `poplar_env` with the tools that can be installed through conda, as well as download the tools that are not installed with conda (BLAST, RAxML-NG, ASTRAL-Pro). The files will be downloaded to the current directory, and the paths will be added in the worker initialization through `parsl/config.py`.

As an alternative, Docker may also be used for installation.

### Dependencies to run `setup.sh`:

- [conda 23.11.0](https://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html)
- [wget 1.19.5](https://www.gnu.org/software/wget/)
- [gcc and g++ 8.5.0](https://gcc.gnu.org/)
- [git 2.39.3](https://git-scm.com/)
- [tar 1.30](https://www.gnu.org/software/tar/)
- [unzip 6.00](https://infozip.sourceforge.net/)
- [sed 4.5](https://www.gnu.org/software/sed/)

### Required dependencies, installed in `setup.sh`:

- [Python 3.10](https://www.python.org/downloads/)
- [Parsl 2024.9.2](https://parsl.readthedocs.io/en/stable)
- [numpy 2.1.1](https://numpy.org/)
- [sklearn 1.5.1](https://scikit-learn.org/stable/index.html)
- [biopython 1.84](https://biopython.org/docs/1.75/api/Bio.html)
- [orfipy 0.0.4](https://pypi.org/project/orfipy/)
- [BLAST 2.16.0](https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/)
- [MAFFT 7.526](https://mafft.cbrc.jp/alignment/software/)
- [RAxML-NG 1.2.2](https://github.com/amkozlov/raxml-ng)
- [ASTRAL-Pro3](https://github.com/chaoszhang/ASTER)

#### Optional for downloading NCBI data, installed in `setup.sh`:

- [NCBI Command-line Tools 16.27.2](https://www.ncbi.nlm.nih.gov/datasets/docs/v2/download-and-install/)

#### Optional for Parsl workflow monitoring, installed in `setup.sh`:

- [Parsl Monitoring](https://parsl.readthedocs.io/en/stable/userguide/monitoring.html)
- [flask 3.0.3](https://palletsprojects.com/projects/flask)
- [flask-sqlalchemy 3.1.1](https://flask-sqlalchemy.readthedocs.io/en/3.1.x/)
- [pandas 2.2.2](https://pandas.pydata.org/)
- [plotly 5.24.1](https://plot.ly/python/)
- [networkx 3.3](https://networkx.github.io/)
- [pydot 3.0.1](https://github.com/erocarrera/pydot)

Using other software versions may not work with Poplar.

### Alternative Installation with Docker

A dockerfile is included, which can be built and run using:

```
sudo docker build -t poplar_env_image .
sudo docker run -it poplar_env_image
```

## Parsl Configuration

Parsl is a Python package used to manage parallel tasks. It can manage multiple Slurm job allocations, as it does in Poplar, and oversees running parallel and sequential tasks in Poplar.

Parsl requires a configuration file with information required to launch the tasks. Information about the scope of options is available in Parsl's documentation, and the file in `parsl/config.py` offers a template to build on for Poplar. Parsl uses "block" structures, an abstraction the [Parsl documentation](https://parsl.readthedocs.io/en/stable/userguide/execution.html) defines as "the most basic unit of resources to be acquired from a provider." In the Slurm context, a block can be one or more nodes, and the number of blocks can change throughout the execution.

The key things that need to be changed when moving to a new machine are:

- conda environment activation, in `worker_init` (automatically set with `setup.sh`)
- PATH for tools that are not installed with conda, in `worker_init` (automatically set with `setup.sh`)
- partition name for the slurm partition to be used, in provider `partition`
- nodes per block, maximum blocks, walltime, also within provider, based on the machine and the job being run

Parsl allows Poplar to be run on systems other than those with Slurm, and Parsl's documentation describes how to use other types of providers, including cloud and local execution. [Parsl Documentation](https://parsl.readthedocs.io/en/stable/userguide/execution.html) describes the variety of options.

## Input

The required argument for Poplar is a JSON file directing the software to the files with genetic information. [See here for information on downloading data from NCBI or formatting your own input file.](documentation/downloading_data.md)

### Running the Pipeline

After installing using `setup.sh` and updating `parsl/config.py`, change the header and input in `poplar.sh`. The partion name and time limit are machine dependent. The path to the JSON file also needs be included as an argument for the Python script.

Options for Poplar are available in the help menu, by running `parsl/main.py -h`.

#### Options:

- `-h` or `--help`: show help message and exit
- `-o` or `--output_file`: name of output file. Defaults to `output.tree`
- `-e` or `--blast_evalue`: set maximum evalue for blastn search in finding related gene sequences. Defaults to 1e-20
- `-t` or `--max_trees`: set the maximum number of gene trees to construct. Defaults to 50
- `-g` or `--max_group_size`: set the maximum number of sequences permitted in a gene group. Defaults to 100

## Output

The pipeline will create a new directory within the current directory to store all the temporary files. One output tree will be named `job_{jobnum}.tree` and be in the current directory. The labels of this tree will match the accession IDs. If `dataset_catalog.json` contains a file of type `DATA_TABLE`, then Aasecond output tree named `job_{jobnum}_scinames.tree` will replace the accession IDs with the scientific names. This may be easier to read, but it will not differentiate between multiple instances of a single species, and it will not rename any species without an entry in the data table.

## Limitations

This tool works only on Linux/Unix machines due to dependencies. The provided scripts show running with Slurm Workload Manager, and users can adapt the Parsl configuration to work with other compatible managers.

If certain pre-compiled executables (such as for seqkit) cannot run on the provided architecture, there will be errors. These can be resolved by replacing the executables in their current locations.

Jobs spawn other jobs and then wait for their completion. If jobs are forced to wait in the queue beyond the time limit of the originating job, then the pipeline might crash.

## Steps

1. Gene and ORF Location

	- The first step is to extract genes and possible genes from each input organism. If coding sequences are included in the input, they are used. If not, then orfipy is used.

2. Grouping Genes and ORFs

	- All genes and ORFs are combined into a BLAST database, available for search. Following the creation of the database, the databaes is queried for each input sequence. This results in a distance between it and the most similar sequences (the match to itself then excluded).
	- Using the distances from BLAST, a distance matrix is created and used with DBSCAN to create groupings. By default, BLAST will use a maximum distance of 1e-20, and this threshold can be changed via `-e` or `--blast_evalue`

3. Gene Trees

	- The sequences in each group are aligned using MAFFT.
	- The sequence alignments are given to RAxML to generate gene trees.

4. Species Tree

	- The RAxML gene trees are given to ASTRAL-Pro to generate a single species tree.

### Instructions for Generating NCBI Tree

The tests in our paper compare the trees generated by this pipeline to NCBI's taxonomy. Creating that tree requires downloading data from NCBI's website and through their command line tools. The provided script `reference_tree.sh` downloads data from NCBI and creates a Newick tree with the available information on the spcies. In order to use the script, visit [NCBI's Genome Browser](https://www.ncbi.nlm.nih.gov/datasets/genome) and search for the names or IDs of the species of interest. For our tests, we selected only the reference genomes. Then, download the table. This table includes the GenBank reference numbers. The first column of the table will be GenBank IDs, which will be used for searching NCBI's database for the taxonomy.

### Checkpointing

Parsl supports checkpointing, which is used in Poplar. When each task completes, Parsl stores the result of the task. In most cases, this is the path to a file that contains the results. If the managing job times out or a task fails, running Poplar again with the same arguments in the same location will identify the previous results and pick up execution from that point. If a task failed due to bad arguments, then this will not resolve the issue, but if there is an issue with the executing the task, such as an incorrectly installed dependency or misplaced file, rerunning with the fix and the same arguments will typically resolve the issue without rerunning the full pipeline. Between the two runs, the files created in the directory beginning with `parsl_tmp` and the checkpoint information in `runinfo` must not be deleted or moved.

### Hardware Requirements
 
Parsl operates through the process where the Python script is initiated managing blocks of hardware resources. Because of the requirement of the managing task, a CPU is required to manage the rest of the processes. The requirement of processors and memory is based on the desired degree of parallelism. It is possible to run Poplar with a low number of CPUs, but it is designed to use a large set of CPUs.
 
When testing the [Kickxellomycotina dataset](https://mycocosm.jgi.doe.gov/mycocosm/species-tree/tree;MIdizk?organism=kickxellomycotina) from JGI's MycoCosm with 500 species trees, only 46GB of RAM was required across 270 CPUs.

## Planned Improvements

- Analysis of optimal gene sequence group size. Currently is required to be between 4 and 99
- Options of software for each step
- Performance improvement of selecting ORFs for sequence groups
- Improvement on sequence group selection
- Assess HDBSCAN in comparison to DBSCAN for performance and accuracy
- Option to use HMMER for clustering
- Pass RAxML options to user in configuration file

## Citing Poplar

Once a preprint is available, the citation will be here.

## Copyright

Copyright 2024 National Technology & Engineering Solutions of Sandia, LLC (NTESS). Under the terms of Contract DE-NA0003525 with NTESS, the U.S. Government retains certain rights in this software.
