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

# Create .csv files for linking
#echo "Creating OSM .csv files..."
java -jar target/Topos-parser-1.0-SNAPSHOT.jar prepare_for_linking OSM "$osm_dir/${input}/${input,,}_wikidata.nt" "$osm_dir/${input}/${input,,}_admin_1.csv" 4
print_lines "$osm_dir/${input}/${input,,}_admin_1.csv"
java -jar target/Topos-parser-1.0-SNAPSHOT.jar prepare_for_linking OSM "$osm_dir/${input}/${input,,}_wikidata.nt" "$osm_dir/${input}/${input,,}_admin_2.csv" 6
print_lines "$osm_dir/${input}/${input,,}_admin_2.csv"

#echo "Creating GAUL .csv files..."
java -jar target/Topos-parser-1.0-SNAPSHOT.jar prepare_for_linking GAUL "$gaul_dir/${input}/${input}_fixed.nt" "$gaul_dir/${input}/gaul_${input,,}_admin_1.csv" 1
print_lines "$gaul_dir/${input}/gaul_${input,,}_admin_1.csv"
java -jar target/Topos-parser-1.0-SNAPSHOT.jar prepare_for_linking GAUL "$gaul_dir/${input}/${input}_fixed.nt" "$gaul_dir/${input}/gaul_${input,,}_admin_2.csv" 2
print_lines "$gaul_dir/${input}/gaul_${input,,}_admin_2.csv"

# Call pyjedai workflow
python3  "pyjedai_workflow.py" --d1 "$gaul_dir/${input}/gaul_${input,,}_admin_1.csv" --d2 "$osm_dir/${input}/${input,,}_admin_1.csv" --output "$osm_dir/${input}/linking_admin_1.csv"
python3  "pyjedai_workflow.py" --d1 "$gaul_dir/${input}/gaul_${input,,}_admin_2.csv" --d2 "$osm_dir/${input}/${input,,}_admin_2.csv" --output "$osm_dir/${input}/linking_admin_2.csv"
