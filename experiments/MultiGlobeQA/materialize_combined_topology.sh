#!/usr/bin/env bash
set -euo pipefail

# Usage: ./materialize_entity_country_topology.sh <entities.nt> <countries.nt> <output_mappings.nt>
# Source = WorldKG + OSMH3KG entity geometry triples (provided as one entities.nt)
# Target = countries.nt. No _no filtering, no ISO3 pattern.

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <entities.nt> <countries.nt> <output_mappings.nt>" >&2
  exit 2
fi

source_nt="$(realpath "$1")"
target_nt="$(realpath "$2")"
output_nt="$(realpath -m "$3")"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
spatial_script="$script_dir/jedai_spatial_pipeline.sh"
map_script="$script_dir/jedai_map.sh"
interlinking_jar="$script_dir/geospatialinterlinking-1.0-SNAPSHOT-jar-with-dependencies.jar"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
fail() { log "ERROR: $*" >&2; exit 1; }

for f in "$source_nt" "$target_nt" "$spatial_script" "$map_script" "$interlinking_jar"; do
  [[ -f "$f" ]] || fail "Missing file: $f"
done
[[ -s "$source_nt" ]] || fail "Empty source: $source_nt"
[[ -s "$target_nt" ]] || fail "Empty target: $target_nt"
[[ "$output_nt" != "$source_nt" && "$output_nt" != "$target_nt" ]] || fail "Output must differ from inputs"

work_dir="$(mktemp -d)"
trap 'rm -rf -- "$work_dir"' EXIT

# Stable names matter: jedai_spatial_pipeline.sh writes these beside each input.
source_copy="$work_dir/source.nt"
target_copy="$work_dir/target.nt"
source_csv="$work_dir/source_no_crs_geo_only.csv"
target_csv="$work_dir/target_no_crs_geo_only.csv"
source_tsv="$work_dir/source_no_crs_geo_only.tsv"
target_tsv="$work_dir/target_no_crs_geo_only.tsv"
raw_mappings="$work_dir/mapping_ids.nt"
uri_mappings="$work_dir/mapping_ids_map.nt"

log "Source: $source_nt"
log "Target: $target_nt"
log "Output: $output_nt"
log 'Preparing separate source and target datasets'
cp -- "$source_nt" "$source_copy"
cp -- "$target_nt" "$target_copy"
log "Source triples: $(wc -l < "$source_copy")"
log "Target triples: $(wc -l < "$target_copy")"

log 'Preprocessing entity geometries'
"$spatial_script" "$source_copy"
log 'Preprocessing country geometries'
"$spatial_script" "$target_copy"
for f in "$source_csv" "$target_csv" "$source_tsv" "$target_tsv"; do
  [[ -f "$f" ]] || fail "Preprocessing output missing: $f"
done

log 'Interlinking entity geometries (source) against countries (target)'
(
  cd "$work_dir"
  java -cp "$interlinking_jar" workflowManager.CommandLineInterface \
    custom "$source_csv" "$target_csv" "$raw_mappings"
)
[[ -f "$raw_mappings" ]] || fail "Interlinker output missing: $raw_mappings"
log "Raw mappings: $(wc -l < "$raw_mappings")"

log 'Mapping numeric IDs to URI references'
"$map_script" "$raw_mappings" "$source_tsv" "$target_tsv"
[[ -f "$uri_mappings" ]] || fail "URI mapping output missing: $uri_mappings"
mkdir -p "$(dirname "$output_nt")"
mv -f -- "$uri_mappings" "$output_nt"
log "Completed: $(wc -l < "$output_nt") entity-to-country mappings"

