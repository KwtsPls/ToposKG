#!/bin/bash
set -euo pipefail

# Check for required arguments
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <continent> <country>"
  exit 1
fi

input1="$1"
input2="$2"

mkdir -p "${input2}"

# Function to wrap grep results into a FeatureCollection
process_file() {
  output_file=$1

  tmp_file=$(mktemp)
  if tail -n1 "$output_file" | grep -q '},\s*$'; then
    sed '$ s/},\s*$/}/' "$output_file" > "$tmp_file"
  else
    cp "$output_file" "$tmp_file"
  fi

  echo "]}" >> "$tmp_file"
  mv "$tmp_file" "$output_file"
}

geofabrik="${input2// /-}"

wget -O "${input2}/${geofabrik,,}-latest.osm.pbf" \
  "https://download.geofabrik.de/${input1}/${geofabrik,,}-latest.osm.pbf"

osmium export "${input2}/${geofabrik,,}-latest.osm.pbf" \
  -o "${input2}/${input2,,}-all.geojson"

grep '"natural":"water"' "${input2}/${input2,,}-all.geojson" > "${input2}/${input2,,}-mixed.geojson" || true
echo '{"type":"FeatureCollection", "features": [' > "${input2}/${input2,,}_water.geojson"
cat "${input2}/${input2,,}-mixed.geojson" >> "${input2}/${input2,,}_water.geojson"

grep '"natural":"wood"' "${input2}/${input2,,}-all.geojson" > "${input2}/${input2,,}-mixed.geojson" || true
echo '{"type":"FeatureCollection", "features": [' > "${input2}/${input2,,}_forest.geojson"
cat "${input2}/${input2,,}-mixed.geojson" >> "${input2}/${input2,,}_forest.geojson"

grep '"amenity":' "${input2}/${input2,,}-all.geojson" > "${input2}/${input2,,}-mixed.geojson" || true
echo '{"type":"FeatureCollection", "features": [' > "${input2}/${input2,,}_poi.geojson"
cat "${input2}/${input2,,}-mixed.geojson" >> "${input2}/${input2,,}_poi.geojson"

rm -rf \
  "${input2}/${geofabrik,,}-latest.osm.pbf" \
  "${input2}/${input2,,}-all.geojson" \
  "${input2}/${input2,,}-mixed.geojson" \
  "${input2}/${input2,,}.geojson"

process_file "${input2}/${input2,,}_water.geojson"
process_file "${input2}/${input2,,}_forest.geojson"
process_file "${input2}/${input2,,}_poi.geojson"
