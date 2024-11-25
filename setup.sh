#!/bin/bash

# Run this in the location you would like to download the dependencies

# Download into "dependencies" directory
mkdir -p dependencies
cd dependencies

if ! conda info --envs | grep -q "^poplar_env\b"; then
  conda env create -f ../poplar_env.yml --solver classic
  conda activate poplar_env
else
  conda activate poplar_env
  conda env update --file ../poplar_env.yml --prune --solver classic
fi
# OR create with
# if poplar_env does not exist, create it
#conda config --add channels conda-forge
#if ! conda info --envs | grep -q "^poplar_env\b"; then
#  conda create -n poplar_env pip python=3.10 numpy=2.1.1 scikit-learn=1.5.1 biopython=1.84 parsl=2024.9.2 bioconda::orfipy=0.0.4 mafft=7.526 ncbi-datasets-cli=16.27.2 
#fi
#conda activate poplar_env
#conda install pip python=3.10 numpy=2.1.1 scikit-learn=1.5.1 biopython=1.84 parsl=2024.9.2 bioconda::orfipy=0.0.4 mafft=7.526 ncbi-datasets-cli=16.27.2
pip install 'parsl[monitoring]'
#conda install flask=3.0.3 conda-forge::flask-sqlalchemy=3.1.1 pandas=2.2.2 plotly=5.24.1 networkx=3.3 pydot=3.0.1 # for monitoring

EXTEND_PATH=""

# Find the most recent version at: https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/LATEST/
if [ ! -f ncbi-blast-2.16.0+-x64-linux.tar.gz ]; then
  wget https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.16.0/ncbi-blast-2.16.0+-x64-linux.tar.gz
fi
echo "48f66c9e01ea5136e381b2bf6fc62036 ncbi-blast-2.16.0+-x64-linux.tar.gz" | md5sum -c --status
if [ "$?" != 0 ]; then
  echo "Removing and re-downloading NCBI BLAST due to difference in checksum"
  rm ncbi-blast-2.16.0+-x64-linux.tar.gz
  wget https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.16.0/ncbi-blast-2.16.0+-x64-linux.tar.gz
fi
tar --skip-old-files -xf ncbi-blast-2.16.0+-x64-linux.tar.gz && cd ncbi-blast-2.16.0+/bin && \
echo "Add to PATH: " $PWD && export PATH=$PATH:$PWD && EXTEND_PATH=$EXTEND_PATH:$PWD && cd ../..

if [ ! -f raxml-ng_v1.2.2_linux_x86_64.zip ]; then
  wget https://github.com/amkozlov/raxml-ng/releases/download/1.2.2/raxml-ng_v1.2.2_linux_x86_64.zip 
fi
echo "53396a5882b786c5771dbf9c6f9796ce raxml-ng_v1.2.2_linux_x86_64.zip" | md5sum -c --status
if [ "$?" != 0 ]; then
  echo "Removing and re-downloading RAxML-NG due to difference in checksum"
  rm raxml-ng_v1.2.2_linux_x86_64.zip
  wget https://github.com/amkozlov/raxml-ng/releases/download/1.2.2/raxml-ng_v1.2.2_linux_x86_64.zip
fi
unzip -u raxml-ng_v1.2.2_linux_x86_64.zip && echo "Add to PATH: " $PWD && export PATH=$PATH:$PWD && EXTEND_PATH=$EXTEND_PATH:$PWD

# ASTRAL can be downloaded prebuilt or built from the it repo. Prebuilt requires GLIBC 2.34
if [ ! -d "ASTER" ]; then
  git clone https://github.com/chaoszhang/ASTER.git
fi
cd ASTER && git pull && make && export PATH=$PATH:$PWD/bin && EXTEND_PATH=$EXTEND_PATH:$PWD/bin && cd ..

# Automatically updates worker_init in config.py
sed -i -E "s%worker_init\s*=\s*'([^']*)'%worker_init='conda activate poplar_env; export PATH=\$PATH:$EXTEND_PATH'%gm;t" ../parsl/config.py
