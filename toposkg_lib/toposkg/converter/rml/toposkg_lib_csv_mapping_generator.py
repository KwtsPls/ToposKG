import os
import pandas as pd
import hashlib
from converter.rml import toposkg_lib_triples_map
from converter.rml import toposkg_lib_mapping_builder

class CSVMappingGenerator():
    def __init__(self, ontology_uri, resource_uri):
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        pass

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
        df["_pyrml_mapper_generated_id"] = range(1, len(df) + 1)

        base_name = os.path.basename(input_csv)
        file_hash = hashlib.blake2b(base_name.encode("utf-8"), digest_size=16).hexdigest()
        output_csv = os.path.join(
            os.path.dirname(input_csv),
            f"_{file_hash}{base_name}"
        )

        # Save to new CSV
        df.to_csv(output_csv, index=False)
        return output_csv
    
    # CSV METHODS
    def generate_for_csv(self, input_data_source):
        triples_map = toposkg_lib_triples_map.TriplesMap(self.ontology_uri,self.resource_uri)
        triples_map.add_logical_source(input_data_source,"ql:CSV")
        triples_map.add_subject_map("NAME","county")
        column_info = self.get_csv_column_info(input_data_source)
        for k,v in column_info.items():
            triples_map.add_predicate_object_map(k.replace(" ","_"),k,v)
        
        builder = toposkg_lib_mapping_builder.RMLBuilder(self.ontology_uri,self.resource_uri,[triples_map])
        print(builder.export_as_string())

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
        intermediate_file = self.add_generated_id(input_data_source)
        triples_map = toposkg_lib_triples_map.TriplesMap(self.ontology_uri,self.resource_uri)
        triples_map.add_logical_source(intermediate_file,"ql:CSV")
        triples_map.add_subject_map("_pyrml_mapper_generated_id",None)
        column_info = self.get_csv_column_info(intermediate_file)
        for k,v in column_info.items():
            triples_map.add_predicate_object_map(k.replace(" ","_"),k,v)
        
        builder = toposkg_lib_mapping_builder.RMLBuilder(self.ontology_uri,self.resource_uri,[triples_map])
        return builder.export_as_string()