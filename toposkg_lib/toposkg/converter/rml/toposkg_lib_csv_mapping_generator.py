import os
import pandas as pd
import hashlib
from toposkg.converter.rml import toposkg_lib_triples_map
from toposkg.converter.rml import toposkg_lib_mapping_builder

class CSVMappingGenerator():
    def __init__(self, ontology_uri, resource_uri):
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        self.generated_id = None
        self.maps = []

    def add_generated_id(self, input_csv: str) -> None:
        """
        Reads a CSV file, adds an ID column named '_pyrml_mapper_generated_id',
        and writes the result to a new CSV file.

        Parameters:
            input_csv (str): Path to the input CSV file.
            output_csv (str): Path where the new CSV with ID column will be saved.
        """
        # Load CSV
        df = pd.read_csv(input_csv)

        # Add ID column starting from 1
        df[self.generated_id] = range(1, len(df) + 1)

        base_name = os.path.basename(input_csv)
        file_hash = hashlib.blake2b(base_name.encode("utf-8"), digest_size=16).hexdigest()
        output_csv = os.path.join(
            os.path.dirname(input_csv),
            f"_{file_hash}{base_name}"
        )

        # Save to new CSV
        df.to_csv(output_csv, index=False)
        return output_csv
        

    def get_csv_column_info(self, filepath):
        """
        Reads a CSV and returns a dictionary of column names and inferred data types 
        based on the first row of data.
        """
        # Read CSV normally (with headers)
        df = pd.read_csv(filepath)
        
        # Take the first data row
        first_row = df.iloc[0]

        # Type inference function
        def infer_dtype(value):
            if isinstance(value, bool):
                return "bool"   
            elif isinstance(value, int):
                return "int"
            elif isinstance(value, float):
                return "float"
            else:
                return "string"  

        # Map each column to its inferred type
        col_info = {col: infer_dtype(first_row[col]) for col in df.columns}
        return col_info
        

    # JSON METHODS
    def generate_default_mapping(self, input_data_source):
        base_name = os.path.basename(input_data_source)
        file_hash = hashlib.blake2b(base_name.encode("utf-8"), digest_size=16).hexdigest()
        self.generated_id = file_hash + "_pyrml_mapper_generated_id"

        intermediate_file = self.add_generated_id(input_data_source)
        triples_map = toposkg_lib_triples_map.TriplesMap(self.ontology_uri,self.resource_uri)
        triples_map.add_logical_source(intermediate_file,"ql:CSV")
        triples_map.add_subject_map(self.generated_id ,None)
        column_info = self.get_csv_column_info(intermediate_file)
        for k,v in column_info.items():
            triples_map.add_predicate_object_map(k.replace(" ","_"),k,v)
        
        self.maps = [triples_map]