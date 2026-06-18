################################
# Dockerfile for DA4DTE's KG   #
# DI @ UoA                     #
#                              #
# Java 11                      #
# graphdb 10.6.3               #
################################

FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

ENV PORT=7200
ENV GRAPH_DB_VERSION=10.6.3

ARG ZENODO_RECORD=20071499
ARG KG_FILE=toposkg.nt.gz

# INSTALL PREREQUISITIES
RUN apt-get update \
 && apt-get install -y \
    wget \
    openjdk-11-jdk \
    curl \
    unzip \
    gzip \
    gnupg2 \
    ca-certificates \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Download and extract GraphDB
RUN wget "https://maven.ontotext.com/repository/owlim-releases/com/ontotext/graphdb/graphdb/${GRAPH_DB_VERSION}/graphdb-${GRAPH_DB_VERSION}-dist.zip" \
 && unzip "graphdb-${GRAPH_DB_VERSION}-dist.zip" \
 && rm "graphdb-${GRAPH_DB_VERSION}-dist.zip"

# Copy repository configuration
COPY template.ttl .

# Download, decompress, and preload the knowledge graph
RUN curl -fL --retry 5 --retry-delay 10 \
      -o "${KG_FILE}" \
      "https://zenodo.org/api/records/${ZENODO_RECORD}/files/${KG_FILE}/content" \
 && gunzip "${KG_FILE}" \
 && ./graphdb-${GRAPH_DB_VERSION}/bin/importrdf preload \
      -c template.ttl \
      "${KG_FILE%.gz}" \
 && rm -f "${KG_FILE%.gz}"

EXPOSE 7200
EXPOSE 7300

ENTRYPOINT ["sh", "-c", "./graphdb-${GRAPH_DB_VERSION}/bin/graphdb"]
