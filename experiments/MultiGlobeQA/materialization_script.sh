
#!/usr/bin/env bash
set -euo pipefail

# Usage:
# ./materialize_topology.sh <input.nt> <output.nt> [no_pattern]

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "Usage: $0 <input.nt> <output.nt> [no_pattern]"
    exit 1
fi

input_nt="$(realpath "$1")"
output_nt="$(realpath -m "$2")"
no_pattern="${3:-_no}"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

spatial_script="$script_dir/jedai_spatial_pipeline.sh"
map_script="$script_dir/jedai_map.sh"
interlinking_jar="$script_dir/geospatialinterlinking-1.0-SNAPSHOT-jar-with-dependencies.jar"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

check_file() {
    if [[ ! -f "$1" ]]; then
        echo "ERROR: Missing file: $1" >&2
        exit 1
    fi
}

check_file "$input_nt"
check_file "$spatial_script"
check_file "$map_script"
check_file "$interlinking_jar"

if [[ "$input_nt" == "$output_nt" ]]; then
    echo "ERROR: Input and output must differ." >&2
    exit 1
fi

# Temporary workspace
work_dir="$(mktemp -d)"

cleanup() {
    if [[ -n "${work_dir:-}" && -d "$work_dir" ]]; then
        rm -rf -- "$work_dir"
    fi
}

trap cleanup EXIT

# Input datasets
no_upper_nt="$work_dir/no_upper.nt"
country_nt="$work_dir/country.nt"

# Generated CSV and TSV files
no_csv="$work_dir/no_upper_no_crs_geo_only.csv"
country_csv="$work_dir/country_no_crs_geo_only.csv"

no_tsv="$work_dir/no_upper_no_crs_geo_only.tsv"
country_tsv="$work_dir/country_no_crs_geo_only.tsv"

# Interlinking files
mapping_ids_nt="$work_dir/mapping_ids.nt"
mapping_ids_map_nt="$work_dir/mapping_ids_map.nt"

log "Starting spatial materialization"
log "Input: $input_nt"
log "Output: $output_nt"

# --------------------------------------------------
# STEP 1: Prepare datasets
# --------------------------------------------------

log "Step 1/4: Preparing datasets..."

grep -F "$no_pattern" "$input_nt" > "$no_upper_nt" || true

cp "$input_nt" "$country_nt"

if [[ ! -s "$no_upper_nt" ]]; then
    echo "ERROR: No triples matching '$no_pattern'." >&2
    exit 1
fi

log "Source triples: $(wc -l < "$no_upper_nt")"
log "Target triples: $(wc -l < "$country_nt")"

# --------------------------------------------------
# STEP 2: Spatial preprocessing
# --------------------------------------------------

log "Step 2/4: Running spatial preprocessing..."

"$spatial_script" "$no_upper_nt"
"$spatial_script" "$country_nt"

check_file "$no_csv"
check_file "$country_csv"
check_file "$no_tsv"
check_file "$country_tsv"

# --------------------------------------------------
# STEP 3: Geospatial interlinking
# --------------------------------------------------

log "Step 3/4: Discovering spatial relationships..."

(
    cd "$work_dir"

    java -cp "$interlinking_jar" \
        workflowManager.CommandLineInterface \
        custom \
        "$no_csv" \
        "$country_csv" \
        "$mapping_ids_nt"
)

check_file "$mapping_ids_nt"

log "Discovered relationships: $(wc -l < "$mapping_ids_nt")"

# --------------------------------------------------
# STEP 4: Map IDs to entity URIs
# --------------------------------------------------

log "Step 4/4: Mapping relationship IDs to entities..."

"$map_script" \
    "$mapping_ids_nt" \
    "$no_tsv" \
    "$country_tsv"

check_file "$mapping_ids_map_nt"

log "Mapped relationships: $(wc -l < "$mapping_ids_map_nt")"

# --------------------------------------------------
# FINAL OUTPUT
# --------------------------------------------------

log "Moving mappings to output..."

mkdir -p "$(dirname "$output_nt")"

mv -f "$mapping_ids_map_nt" "$output_nt"

log "Completed successfully."
log "Final mappings: $(wc -l < "$output_nt")"
log "Output: $output_nt"

# All remaining temporary files are deleted by trap.

