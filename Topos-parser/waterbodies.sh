#!/bin/bash

input="$1"
while IFS= read -r line
do
  echo "$line"
  prefix="${line// /_}"
  java -Xmx100g -jar target/GADM-parser-1.0-SNAPSHOT.jar water  "/home/kwts/Desktop/SpatialKG/data/OSM/countries/waterbodies/$line/${line,,}_water.geojson" "/home/kwts/Desktop/SpatialKG/data/OSM/countries/waterbodies/$line/${line,,}_water.nt" "${prefix,,}" 
done < "$input"
