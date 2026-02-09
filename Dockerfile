FROM python:3.11-slim

# Install system dependencies
# git: required by PyDriller for git history analysis
# default-jre-headless: required by PMD/CPD for clone detection
# jq: for parsing GitHub event payload
# curl/unzip: for downloading PMD
RUN apt-get update && \
    apt-get install -y --no-install-recommends git default-jre-headless jq curl unzip && \
    rm -rf /var/lib/apt/lists/*

# Download PMD for clone detection
ENV PMD_VERSION=7.9.0
RUN curl -sSL "https://github.com/pmd/pmd/releases/download/pmd_releases%2F${PMD_VERSION}/pmd-dist-${PMD_VERSION}-bin.zip" -o /tmp/pmd.zip && \
    unzip -q /tmp/pmd.zip -d /opt && \
    mv /opt/pmd-bin-${PMD_VERSION} /opt/pmd && \
    rm /tmp/pmd.zip
ENV PMD_HOME=/opt/pmd

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Create __init__.py files for packages that need them
RUN touch analysis/__init__.py git_providers/__init__.py rag/__init__.py utils/__init__.py

# Make entrypoint executable
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
