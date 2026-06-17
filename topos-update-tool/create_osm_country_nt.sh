#!/usr/bin/env bash
set -euo pipefail

print_lines () {
  lines=$( wc -l <"$1" )
  echo "$lines"
}

if [ "$#" -ne 4 ] && [ "$#" -ne 5 ]; then
  echo "Usage: $0 <country> <prefix> <osm_countries_root_dir> <parser_jar_path> [fixer_script_path]"
  echo ""
  echo "Example:"
  echo "  $0 'Algeria' dza data/osm/countries parser.jar fixer.py"
  exit 1
fi

input="$1"
prefix="$2"
osm_dir="$3"
parser_jar="$4"

if [ "$#" -eq 5 ]; then
  fixer_script="$5"
else
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  fixer_script="$script_dir/fixer.py"
fi

base_dir="$osm_dir/${input}"

wikidata_geojson="$base_dir/${input,,}_wikidata.geojson"
no_wikidata_geojson="$base_dir/${input,,}_no_wikidata.geojson"

wikidata_nt="$base_dir/${input,,}_wikidata.nt"
no_wikidata_nt="$base_dir/${input,,}_no_wikidata.nt"
merged_nt="$base_dir/${input,,}.nt"

if [ ! -f "$parser_jar" ]; then
  echo "ERROR: parser jar not found: $parser_jar"
  exit 1
fi

if [ ! -f "$fixer_script" ]; then
  echo "ERROR: fixer.py not found: $fixer_script"
  exit 1
fi

if [ ! -d "$base_dir" ]; then
  echo "ERROR: OSM country directory not found: $base_dir"
  exit 1
fi

for file in "$wikidata_geojson" "$no_wikidata_geojson"; do
  if [ ! -f "$file" ]; then
    echo "ERROR: expected OSM GeoJSON file not found: $file"
    exit 1
  fi
done

echo "Creating OSM .ntriples for $input with prefix $prefix..."

java -jar "$parser_jar" osm "$wikidata_geojson" "$wikidata_nt" "$prefix"
java -jar "$parser_jar" osm "$no_wikidata_geojson" "$no_wikidata_nt" "${prefix}_no"

cat "$wikidata_nt" "$no_wikidata_nt" > "$merged_nt"

rm -rf "$wikidata_nt" "$no_wikidata_nt"

echo "Created:"
echo "  $merged_nt"
echo "Lines before fixing/validation:"
print_lines "$merged_nt"

echo "Running fixer.py:"
echo "  python3 $fixer_script $merged_nt"
python3 "$fixer_script" "$merged_nt"

echo "Running IRI validation:"
echo "  java -jar $parser_jar validate_iris $merged_nt"
java -jar "$parser_jar" validate_iris "$merged_nt"

echo "OSM NT fixing and validation complete:"
echo "  $merged_nt"
echo "Lines after fixing/validation:"
print_lines "$merged_nt"
