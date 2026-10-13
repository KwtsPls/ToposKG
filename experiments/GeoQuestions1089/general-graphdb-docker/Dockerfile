
################################
#                              #
# Java 11                      #
# GraphDB 10.6.3               #
################################

FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

ENV PORT=7200
ENV GRAPH_DB_VERSION=10.6.3

# INSTALL PREREQUISITES
RUN apt-get update \
    && apt-get install -y \
       wget \
       openjdk-11-jdk \
       curl \
       unzip \
       gzip \
       gnupg2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Download and extract GraphDB
RUN wget "https://maven.ontotext.com/repository/owlim-releases/com/ontotext/graphdb/graphdb/${GRAPH_DB_VERSION}/graphdb-${GRAPH_DB_VERSION}-dist.zip" \
    && unzip graphdb-${GRAPH_DB_VERSION}-dist.zip \
    && rm graphdb-${GRAPH_DB_VERSION}-dist.zip

# Install GraphDB GeoSPARQL plugin
COPY graphdb-geosparql-plugin-graphdb-plugin.zip /tmp/

# Install GraphDB GeoSPARQL plugin
COPY graphdb-geosparql-plugin-graphdb-plugin.zip /tmp/

RUN rm -rf ./graphdb-${GRAPH_DB_VERSION}/lib/plugins/geosparql-plugin \
    && mkdir -p ./graphdb-${GRAPH_DB_VERSION}/lib/plugins \
    && unzip -o /tmp/graphdb-geosparql-plugin-graphdb-plugin.zip \
       -d ./graphdb-${GRAPH_DB_VERSION}/lib/plugins/ \
    && rm /tmp/graphdb-geosparql-plugin-graphdb-plugin.zip

# Copy the knowledge graph data
COPY data/* .

# Copy repository template
COPY template.ttl .

EXPOSE 7200
EXPOSE 7300

# Preload knowledge graph
RUN ./graphdb-${GRAPH_DB_VERSION}/bin/importrdf preload \
    -c template.ttl *.nt

# Start GraphDB
ENTRYPOINT ["./graphdb-10.6.3/bin/graphdb"]

