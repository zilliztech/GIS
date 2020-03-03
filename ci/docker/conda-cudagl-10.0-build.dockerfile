FROM nvidia/cudagl:10.0-devel-ubuntu18.04

ENV NVIDIA_DRIVER_CAPABILITIES compute,utility,graphics

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends wget \
    git ccache lcov clang-6.0 clang-format-6.0 clang-tidy-6.0  && \
    wget -qO- "https://cmake.org/files/v3.14/cmake-3.14.3-Linux-x86_64.tar.gz" | tar --strip-components=1 -xz -C /usr/local && \
    wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh && \
    ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
    apt-get remove --purge -y && \
    rm -rf /var/lib/apt/lists/*

COPY docker/build_env/gpu/zgis.yml /tmp/zgis.yml

RUN . /opt/conda/etc/profile.d/conda.sh && \
    conda activate base && \
    conda update --all -y && \
    conda env create -f /tmp/zgis.yml && \
    rm /tmp/zgis.yml && \
    conda clean --all -y && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate bash" >> ~/.bashrc
