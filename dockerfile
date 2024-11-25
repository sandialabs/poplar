# Use an official Ubuntu base image
FROM continuumio/miniconda3

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/root/miniconda3/bin:$PATH"

# Copy all files to the container and set the working directory
COPY . /app
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    git \
    build-essential \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Create the poplar_env environment
RUN conda config --add channels conda-forge
RUN conda create -n poplar_env python=3.10 numpy=2.1.1 scikit-learn=1.5.1 biopython=1.84 \
    parsl=2024.9.2 bioconda::orfipy=0.0.4 mafft=7.526 ncbi-datasets-cli=16.27.2 && \
    conda install -n poplar_env flask=3.0.3 conda-forge::flask-sqlalchemy=3.1.1 \
    pandas=2.2.2 plotly=5.24.1 networkx=3.3 pydot=3.0.1 pip && \
    pip install 'parsl[monitoring]'

# Set up BLAST+
RUN wget https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/2.16.0/ncbi-blast-2.16.0+-x64-linux.tar.gz && \
    tar -xf ncbi-blast-2.16.0+-x64-linux.tar.gz && \
    mv ncbi-blast-2.16.0+ /opt/ncbi-blast && \
    rm ncbi-blast-2.16.0+-x64-linux.tar.gz && \
    echo 'export PATH=$PATH:/opt/ncbi-blast/bin' >> /root/.bashrc

# Set up RAxML-NG
RUN wget https://github.com/amkozlov/raxml-ng/releases/download/1.2.2/raxml-ng_v1.2.2_linux_x86_64.zip && \
    unzip raxml-ng_v1.2.2_linux_x86_64.zip -d /opt/raxml-ng && \
    rm raxml-ng_v1.2.2_linux_x86_64.zip && \
    echo 'export PATH=$PATH:/opt/raxml-ng' >> /root/.bashrc

# Set up ASTRAL
RUN git clone https://github.com/chaoszhang/ASTER.git /opt/ASTER && \
    cd /opt/ASTER && \
    make && \
    echo 'export PATH=$PATH:/opt/ASTER/bin' >> /root/.bashrc

# Update Parsl config
RUN sed -i -E "s%worker_init\s*=\s*'([^']*)'%worker_init='conda activate poplar_env; export PATH=\$PATH:/opt/ncbi-blast/bin:/opt/raxml-ng:/opt/ASTER/bin'%gm;t" /app/parsl/config.py
RUN sed -i -E "s%worker_init\s*=\s*'([^']*)'%worker_init='conda activate poplar_env; export PATH=\$PATH:/opt/ncbi-blast/bin:/opt/raxml-ng:/opt/ASTER/bin'%gm;t" /app/parsl/config_local.py

# Set the default shell to bash
SHELL ["/bin/bash", "-c"]

# Activate the environment by default
RUN echo "source activate poplar_env" >> /root/.bashrc

# Set the entrypoint
ENTRYPOINT ["/bin/bash"]
