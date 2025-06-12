#!/bin/bash

# Check for input
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <input>"
  exit 1
fi

input="$1"
base_dir="/home/kwts/Desktop/SpatialKG/data/GeoBoundaries-v2/$input"

# Run GADM-parser create commands
java -jar target/GADM-parser-1.0-SNAPSHOT.jar create "$base_dir/${input}_ADM0.geojson" "$base_dir/0.nt" 0
java -jar target/GADM-parser-1.0-SNAPSHOT.jar create "$base_dir/${input}_ADM1.geojson" "$base_dir/1.nt" 1
java -jar target/GADM-parser-1.0-SNAPSHOT.jar create "$base_dir/${input}_ADM2.geojson" "$base_dir/2.nt" 2

# Concatenate all .nt files into one
cat "$base_dir"/[012].nt > "$base_dir/$input.nt"

# Remove intermediate .nt files
rm -f "$base_dir"/[012].nt

# Run GADM-parser fix
java -jar target/GADM-parser-1.0-SNAPSHOT.jar fix "$base_dir/$input.nt" "$base_dir/${input}_fixed.nt" "AGGR"
