#!/bin/bash

# Check for input
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <input>"
  exit 1
fi

input="$1"
base_dir="$2/$input"

# Run GADM-parser create commands
java -jar target/Topos-parser-1.0-SNAPSHOT.jar create "$base_dir/${input}_ADM1.geojson" "$base_dir/1.nt" 0

# Concatenate all .nt files into one
cat "$base_dir"/[1].nt > "$base_dir/$input.nt"

# Remove intermediate .nt files
rm -f "$base_dir"/[1].nt

