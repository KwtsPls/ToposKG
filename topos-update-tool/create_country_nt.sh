#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <country_name> <countries_root_dir> <parser_jar_path>"
  echo ""
  echo "Example:"
  echo "  $0 'Algeria' data/gaul/countries parser.jar"
  exit 1
fi

country="$1"
countries_root="$2"
parser_jar="$3"

safe_country="$(
  printf "%s" "$country" \
    | sed 's#[/[:space:]]#_#g' \
    | sed 's#[^A-Za-z0-9._-]#_#g'
)"

base_dir="$countries_root/$safe_country"

adm0="$base_dir/${safe_country}_ADM0.geojson"
adm1="$base_dir/${safe_country}_ADM1.geojson"
adm2="$base_dir/${safe_country}_ADM2.geojson"

nt0="$base_dir/0.nt"
nt1="$base_dir/1.nt"
nt2="$base_dir/2.nt"

merged_nt="$base_dir/${safe_country}.nt"
fixed_nt="$base_dir/${safe_country}_fixed.nt"

if [ ! -f "$parser_jar" ]; then
  echo "ERROR: parser jar not found: $parser_jar"
  exit 1
fi

if [ ! -d "$base_dir" ]; then
  echo "ERROR: country directory not found: $base_dir"
  exit 1
fi

for file in "$adm0" "$adm1" "$adm2"; do
  if [ ! -f "$file" ]; then
    echo "ERROR: expected GeoJSON file not found: $file"
    exit 1
  fi
done

echo "Creating NT for $country"

java -jar "$parser_jar" create "$adm0" "$nt0" 0
java -jar "$parser_jar" create "$adm1" "$nt1" 1
java -jar "$parser_jar" create "$adm2" "$nt2" 2

cat "$nt0" "$nt1" "$nt2" > "$merged_nt"

rm -f "$nt0" "$nt1" "$nt2"

java -jar "$parser_jar" fix "$merged_nt" "$fixed_nt" "AGGR"

echo "Created:"
echo "  $merged_nt"
echo "  $fixed_nt"
