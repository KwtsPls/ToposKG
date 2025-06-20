#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

#
# Reading command line arguments
#
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <first_file_to_link> <second_file_to_link> <output_file>"
    exit 1
fi

#
# Preparing source file for interlinking
#
input_file="$1"
base_name="${input_file%.*}"
extension="${input_file##*.}"

# Step 1: Run RemoveEPSGTag
no_crs_file="${base_name}_no_crs.${extension}"
echo "Running RemoveEPSGTag..."
java -cp $SCRIPT_DIR/../jar_libs/DuplicateGeometryRemover-1.0-SNAPSHOT.jar DGR RemoveEPSGTag "$input_file"

# Step 2: Run NTriplesToTSV
geo_only_tsv="${base_name}_no_crs_geo_only.tsv"
echo "Running NTriplesToTSV..."
java -cp $SCRIPT_DIR/../jar_libs/DuplicateGeometryRemover-1.0-SNAPSHOT.jar DGR NTriplesToTSV "$no_crs_file"

# Step 3: Convert TSV to CSV
output_csv="${base_name}_no_crs_geo_only.csv"
echo "Converting TSV to CSV..."
python3 $SCRIPT_DIR/tsv_to_csv.py "$geo_only_tsv" "$output_csv"

echo "Process completed. Output CSV: $output_csv"

#
# Preparing target file for interlinking
#
input_file="$2"
base_name="${input_file%.*}"
extension="${input_file##*.}"

# Step 1: Run RemoveEPSGTag
no_crs_file="${base_name}_no_crs.${extension}"
echo "Running RemoveEPSGTag..."
java -cp $SCRIPT_DIR/../jar_libs/DuplicateGeometryRemover-1.0-SNAPSHOT.jar DGR RemoveEPSGTag "$input_file"

# Step 2: Run NTriplesToTSV
geo_only_tsv_2="${base_name}_no_crs_geo_only.tsv"
echo "Running NTriplesToTSV..."
java -cp $SCRIPT_DIR/../jar_libs/DuplicateGeometryRemover-1.0-SNAPSHOT.jar DGR NTriplesToTSV "$no_crs_file"

# Step 3: Convert TSV to CSV
output_csv_2="${base_name}_no_crs_geo_only.csv"
echo "Converting TSV to CSV..."
python3 $SCRIPT_DIR/tsv_to_csv.py "$geo_only_tsv_2" "$output_csv_2"

echo "Process completed. Output CSV: $output_csv_2"

#
# Geospatial Interlinking
#
java -cp $SCRIPT_DIR/../jar_libs/geospatialinterlinking-1.0-SNAPSHOT-jar-with-dependencies.jar workflowManager.CommandLineInterface custom $output_csv $output_csv_2 $3.nt

#
# Mapping discovered relationships to entities
#
echo "Mapping discovered relationships to entities..."
java -cp $SCRIPT_DIR/../jar_libs/DuplicateGeometryRemover-1.0-SNAPSHOT.jar DGR JedAISpatialMap "$3.nt" "$geo_only_tsv" "$geo_only_tsv_2"