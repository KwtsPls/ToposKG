#!/bin/bash

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

  # Remove trailing comma if present and close the GeoJSON array
  # Create a temp file and process the content
  tmp_file=$(mktemp)
  if tail -n1 "$output_file" | grep -q '},\s*$'; then
    # Remove last comma
    sed '$ s/},\s*$/}/' "$output_file" > "$tmp_file"
  else
    cp "$output_file" "$tmp_file"
  fi

  echo "]}" >> "$tmp_file"
  mv "$tmp_file" "$output_file"
}

# Process each level
geofabrik="${input2// /-}"
wget -O "${input2}/${geofabrik,,}-latest.osm.pbf" "https://download.geofabrik.de/${input1}/${geofabrik,,}-latest.osm.pbf"

osmium export "${input2}/${geofabrik,,}-latest.osm.pbf" -o "${input2}/${input2,,}-all.geojson"
grep "admin_level" "${input2}/${input2,,}-all.geojson" > "${input2}/${input2,,}-mixed.geojson"
grep -v "Point\|LineString" "${input2}/${input2,,}-mixed.geojson" > "${input2}/${input2,,}.geojson"

echo '{"type":"FeatureCollection", "features": [' > "${input2}/${input2,,}_wikidata.geojson"
grep "wikidata" "${input2}/${input2,,}.geojson" >> "${input2}/${input2,,}_wikidata.geojson"

echo '{"type":"FeatureCollection", "features": [' > "${input2}/${input2,,}_no_wikidata.geojson"
grep -v "wikidata" "${input2}/${input2,,}.geojson" >> "${input2}/${input2,,}_no_wikidata.geojson"

rm -rf "${input2}/${input2,,}-latest.osm.pbf" "${input2}/${input2,,}-all.geojson" "${input2}/${input2,,}-mixed.geojson" "${input2}/${input2,,}.geojson"

process_file "${input2}/${input2,,}_wikidata.geojson"
process_file "${input2}/${input2,,}_no_wikidata.geojson"
