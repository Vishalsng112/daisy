FROM ubuntu:24.04

# ------------------------------------------------------------------------------
# Global environment configuration
# ------------------------------------------------------------------------------

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# ------------------------------------------------------------------------------
# Base system dependencies
# - Build tools
# - Python runtime
# - Networking / certificates
# ------------------------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    curl wget make build-essential unzip zip \
    libicu-dev tzdata ca-certificates git openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/* /tmp/*

# ------------------------------------------------------------------------------
# Z3 SMT Solver (pinned version, prebuilt binary)
# ------------------------------------------------------------------------------

ARG Z3_VERSION="4.15.4"
ENV Z3_VERSION=${Z3_VERSION}

RUN set -eux; \
    url="https://github.com/Z3Prover/z3/releases/download/z3-${Z3_VERSION}/z3-${Z3_VERSION}-x64-glibc-2.39.zip"; \
    echo "Downloading Z3 from $url"; \
    curl -L -o z3-${Z3_VERSION}.zip "$url"; \
    unzip z3-${Z3_VERSION}.zip; \
    dir="$(unzip -Z -1 z3-${Z3_VERSION}.zip | head -n1 | cut -d/ -f1)"; \
    echo "Installing Z3 from folder: $dir"; \
    cp -a "$dir"/bin/* /usr/local/bin/; \
    cp -a "$dir"/include/* /usr/local/include/ 2>/dev/null || true; \
    ldconfig; \
    rm -rf /app/z3-${Z3_VERSION}.zip /app/"$dir"

# ------------------------------------------------------------------------------
# .NET SDK (required for Dafny / Laurel tooling)
# ------------------------------------------------------------------------------
ENV DOTNET_ROOT=/usr/share/dotnet
ENV PATH="$DOTNET_ROOT:$PATH"

# INSTALL sdk 8 for dafny fork and 6 for laurel and laurel better
RUN wget https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh && \
    chmod +x /tmp/dotnet-install.sh && \
    /tmp/dotnet-install.sh --channel 8.0 --install-dir $DOTNET_ROOT && \
    /tmp/dotnet-install.sh --channel 6.0 --install-dir $DOTNET_ROOT && \
    ln -sf $DOTNET_ROOT/dotnet /usr/bin/dotnet && \
    rm /tmp/dotnet-install.sh
# ------------------------------------------------------------------------------
# Java (required for Java / Gradle-based tooling)
# ------------------------------------------------------------------------------

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

# ------------------------------------------------------------------------------
# Python virtual environment and dependencies, and jupyter Lab
# ------------------------------------------------------------------------------

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY src/requirements.txt ./src/requirements.txt
COPY src ./src

RUN python3 -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r ./src/requirements.txt \
    && pip install --no-cache-dir notebook ipykernel \
    && python -m ipykernel install --user --name=python --display-name "Python (venv)"

EXPOSE 8888

# ------------------------------------------------------------------------------
# Project source code
# ------------------------------------------------------------------------------

COPY . /app

# ------------------------------------------------------------------------------
# Build research tools
# - Dafny fork
# - Laurel placeholder finders
# ------------------------------------------------------------------------------

RUN cd external/dafny_fork && make

RUN cd external/dafny_laurel_repair/laurel/placeholder_finder \
    && dotnet build placeholder_finder.csproj

RUN cd external/dafny_laurel_repair/laurel/placeholder_finder_better \
    && dotnet build placeholder_finder_laurel_better.csproj

# ------------------------------------------------------------------------------
# Runtime user setup (non-root execution)
# ------------------------------------------------------------------------------

RUN useradd --create-home researcher
RUN mkdir -p /app/temp  /app/images \
    && chown -R researcher:researcher /app/src /app/dataset /app/results /app/temp

USER researcher
ENV HOME=/home/researcher
ENV PATH="/app/external/dafny_fork:/app/external/dafny_laurel_repair:$PATH"

# ------------------------------------------------------------------------------
# Default entrypoint
# - Starts Jupyter Lab for interactive use
# ------------------------------------------------------------------------------

CMD ["bash", "-c", "jupyter lab --ip=0.0.0.0 --port=8888 --no-browser"]