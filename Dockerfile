FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y git && \
    rm -rf /var/lib/apt/lists/*

# Install the RsMetaCheck tool from PyPI
RUN pip install --no-cache-dir rsmetacheck==0.3.5

# Copies scripts into the container
COPY entrypoint.sh /entrypoint.sh
COPY postprocess.py /postprocess.py
RUN chmod +x /entrypoint.sh

# Code file to execute when the docker container starts up
ENTRYPOINT ["/entrypoint.sh"]
