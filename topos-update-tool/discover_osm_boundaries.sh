#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 4 ]; then
    echo "Usage: $0 <country_csv_file> <input_dir> <wikidata_hierarchy_file> <parser_jar_path>"
    exit 1
fi

country_csv_file="$(realpath "$1")"
input_dir="$(realpath "$2")"
wikidata_hierarchy_file="$(realpath "$3")"
parser_jar="$(realpath "$4")"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

spatial_script="$script_dir/jedai_spatial_pipeline.sh"
map_script="$script_dir/jedai_map.sh"
interlinking_jar="$script_dir/geospatialinterlinking-1.0-SNAPSHOT-jar-with-dependencies.jar"

upper_predicate="<http://toposkg.di.uoa.gr/ontology/hasUpperAdminUnit>"

check_exists() {
    local path="$1"
    local label="$2"

    if [ ! -e "$path" ]; then
        echo "ERROR: Missing $label: $path" >&2
        exit 1
    fi
}

check_exists "$country_csv_file" "country CSV file"
check_exists "$input_dir" "input directory"
check_exists "$wikidata_hierarchy_file" "Wikidata hierarchy file"
check_exists "$spatial_script" "jedai_spatial_pipeline.sh"
check_exists "$map_script" "jedai_map.sh"
check_exists "$interlinking_jar" "geospatial interlinking jar"
check_exists "$parser_jar" "parser.jar"

tail -n +2 "$country_csv_file" | while IFS=',' read -r country uri code geofabrik_cont extra; do
    country="$(echo "$country" | sed 's/\r$//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    uri="$(echo "$uri" | sed 's/\r$//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    code="$(echo "$code" | sed 's/\r$//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

    if [ -z "$country" ] || [ -z "$uri" ] || [ -z "$code" ]; then
        echo "Skipping malformed row: country='$country', uri='$uri', code='$code'"
        continue
    fi

    country_dir="$input_dir/$country"

    if [ ! -d "$country_dir" ]; then
        echo "WARNING: Country directory not found, skipping: $country_dir" >&2
        continue
    fi

    country_lower="$(echo "$country" | tr '[:upper:]' '[:lower:]')"

    country_nt="$country_dir/${country_lower}.nt"
    gaul2osm_mappings="$country_dir/${country_lower}_osm_levels.csv"

    if [ ! -f "$country_nt" ]; then
        echo "WARNING: Country .nt file not found, skipping: $country_nt" >&2
        continue
    fi

    if [ ! -f "$gaul2osm_mappings" ]; then
        echo "WARNING: GAUL-to-OSM mappings file not found, skipping: $gaul2osm_mappings" >&2
        continue
    fi

    echo "========================================"
    echo "Processing country: $country"
    echo "Code: $code"
    echo "URI: $uri"
    echo "Input NT: $country_nt"
    echo "GAUL-to-OSM mappings: $gaul2osm_mappings"

    work_dir="$(mktemp -d "$country_dir/.jedai_work_${country_lower}_XXXXXX")"

    cleanup() {
        if [ -n "${work_dir:-}" ] && [ -d "$work_dir" ]; then
            rm -rf "$work_dir"
        fi
    }

    trap cleanup EXIT

    no_upper_nt="$work_dir/${country_lower}_no_upper.nt"
    upper_nt="$work_dir/${country_lower}_upper.nt"
    country_work_nt="$work_dir/${country_lower}_country.nt"

    no_csv="$work_dir/${country_lower}_no_upper_no_crs_geo_only.csv"
    country_csv="$work_dir/${country_lower}_country_no_crs_geo_only.csv"

    no_tsv="$work_dir/${country_lower}_no_upper_no_crs_geo_only.tsv"
    country_tsv="$work_dir/${country_lower}_country_no_crs_geo_only.tsv"

    mapping_ids_nt="$work_dir/${country_lower}_mapping_ids.nt"
    mapping_ids_map_nt="$work_dir/${country_lower}_mapping_ids_map.nt"

    discovered_nt="$work_dir/${country_lower}_discovered.nt"
    upper_admin_nt="$work_dir/${country_lower}_upper_admin_units.nt"

    country_wiki_nt="$work_dir/${country_lower}_wiki.nt"
    country_final_nt="$country_dir/${country_lower}_final.nt"

    grep_pattern="${code}_no"

    echo "Splitting $country_nt using pattern: $grep_pattern"

    grep "$grep_pattern" "$country_nt" > "$no_upper_nt" || true
    grep -v "$grep_pattern" "$country_nt" > "$upper_nt" || true

    # Target materialization input:
    # country = no_upper + upper
    cat "$no_upper_nt" "$upper_nt" > "$country_work_nt"

    echo "Running spatial pipeline on no-upper file..."
    "$spatial_script" "$no_upper_nt"

    echo "Running spatial pipeline on full country file..."
    "$spatial_script" "$country_work_nt"

    check_exists "$no_csv" "generated no-upper CSV"
    check_exists "$country_csv" "generated country CSV"
    check_exists "$no_tsv" "generated no-upper TSV"
    check_exists "$country_tsv" "generated country TSV"

    echo "Running geospatial interlinking: no_upper -> country..."
    (
        cd "$work_dir"
        java -cp "$interlinking_jar" \
            workflowManager.CommandLineInterface \
            custom \
            "$no_csv" \
            "$country_csv" \
            "$mapping_ids_nt"
    )

    check_exists "$mapping_ids_nt" "mapping IDs NT file"

    echo "Mapping discovered relationship IDs to entities..."
    "$map_script" "$mapping_ids_nt" "$no_tsv" "$country_tsv"

    check_exists "$mapping_ids_map_nt" "mapped relationship NT file"

    echo "Ranking intersections..."
    java -jar "$parser_jar" \
        rank_intersections \
        "$country_nt" \
        "$mapping_ids_map_nt" \
        "$discovered_nt"

    check_exists "$discovered_nt" "discovered NT file"

    echo "Extracting sfCovers triples, excluding self-mappings, and replacing predicate..."

    awk -v new_predicate="$upper_predicate" '
        /sfCovers/ {
            subject = $1
            object = $(NF - 1)

            if (subject != object) {
                print subject, new_predicate, object, "."
            }
        }
    ' "$mapping_ids_map_nt" > "$upper_admin_nt"

    check_exists "$upper_admin_nt" "upper-admin materialized NT file"

    echo "Running OSM hierarchy materialization before final merge..."

    java -Xss100M -Xmx100g -jar "$parser_jar" \
        osm_hierarchy \
        "$uri" \
        "$country_nt" \
        "$wikidata_hierarchy_file" \
        "$gaul2osm_mappings" \
        "$country_wiki_nt"

    check_exists "$country_wiki_nt" "country wiki NT file"

    echo "Creating final country file..."

    cat \
        "$country_wiki_nt" \
        "$no_upper_nt" \
        "$discovered_nt" \
        "$upper_admin_nt" \
        > "$country_final_nt"

    check_exists "$country_final_nt" "final country NT file"

    echo "Final output written to: $country_final_nt"

    cleanup
    trap - EXIT

    echo "Finished country: $country"
done

echo "All done."
