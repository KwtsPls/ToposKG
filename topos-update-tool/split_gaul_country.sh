#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 <country_name> <gaul_geojson_root> <output_root> <iso3_code>"
  echo ""
  echo "Example:"
  echo "  $0 'Algeria' data/gaul/geojson data/gaul/countries dza"
  exit 1
fi

country="$1"
gaul_geojson_root="$2"
output_root="$3"
iso3_code="$4"

# "Burkina Faso" -> "Burkina_Faso"
safe_country="$(
  printf "%s" "$country" \
    | sed 's#[/[:space:]]#_#g' \
    | sed 's#[^A-Za-z0-9._-]#_#g'
)"

country_dir="$output_root/$safe_country"
mkdir -p "$country_dir"

process_level() {
  local level="$1"
  local label="$2"

  local input_dir="$gaul_geojson_root/$level"
  local output_file="$country_dir/${safe_country}_${label}.geojson"

  if [ ! -d "$input_dir" ]; then
    echo "WARN: missing GAUL directory: $input_dir"
    return 0
  fi

  mapfile -d '' files < <(find "$input_dir" -type f -name "*.geojson" -print0)

  if [ "${#files[@]}" -eq 0 ]; then
    echo "WARN: no GeoJSON files found in: $input_dir"
    return 0
  fi

  tmp_features="$(mktemp)"

  # Fast filtering.
  #
  # We search for the country name as a JSON string value.
  # Example:
  #   "Algeria"
  #
  # This assumes each GeoJSON feature is stored on one line, which is the
  # same assumption as the original grep-based script.
  grep -hF -- "\"$country\"" "${files[@]}" \
    | sed 's/[[:space:]]*$//' \
    | sed 's/,$//' \
    > "$tmp_features" || true

  # For ADM0 only, add:
  #   "iso3_code": "<code>"
  #
  # This keeps the fast grep-based approach and only edits the matched feature line.
  if [ "$label" = "ADM0" ] && [ -n "$iso3_code" ]; then
    sed -i -E \
      's/("properties"[[:space:]]*:[[:space:]]*\{)/\1"iso3_code":"'"$iso3_code"'",/' \
      "$tmp_features"
  fi

  {
    echo '{"type":"FeatureCollection","features":['

    awk '
      NF {
        if (count > 0) {
          print ","
        }
        printf "%s", $0
        count++
      }
      END {
        if (count > 0) {
          print ""
        }
      }
    ' "$tmp_features"

    echo ']}'
  } > "$output_file"

  count="$(grep -c '"type"[[:space:]]*:[[:space:]]*"Feature"' "$tmp_features" || true)"

  rm -f "$tmp_features"

  echo "Created $output_file with approximately $count features"
}

process_level "L0" "ADM0"
process_level "L1" "ADM1"
process_level "L2" "ADM2"
