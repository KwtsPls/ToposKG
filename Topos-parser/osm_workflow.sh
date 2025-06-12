#!/bin/bash

print_lines () {
  lines=$( wc -l <"$1" )
  echo "$lines"
}

# Check for input
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <country> <prefix>"
  exit 1
fi

input="$1"
prefix="$2"
gaul_dir="$3"
osm_dir="$4"

# Transform OSM .geojson files to .nt files
echo "Creating .ntriples..."
java -jar target/Topos-parser-1.0-SNAPSHOT.jar osm "$osm_dir/${input}/${input,,}_wikidata.geojson"  "$osm_dir/${input}/${input,,}_wikidata.nt" "$prefix"
java -jar target/Topos-parser-1.0-SNAPSHOT.jar osm "$osm_dir/${input}/${input,,}_no_wikidata.geojson"  "$osm_dir/${input}/${input,,}_no_wikidata.nt" "${prefix}_no"
cat "$osm_dir/${input}/${input,,}_wikidata.nt" "$osm_dir/${input}/${input,,}_no_wikidata.nt" > "$osm_dir/${input}/${input,,}.nt"
rm -rf "$osm_dir/${input}/${input,,}_wikidata.nt" "$osm_dir/${input}/${input,,}_no_wikidata.nt"
