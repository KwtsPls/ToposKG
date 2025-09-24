import os
import pandas as pd
from toposkg_lib_triples_map import TriplesMap
from toposkg_lib_mapping_builder import RMLBuilder

class DefaultMappingGenerator():
    def __init__(self, ontology_uri, resource_uri):
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        pass

    # CSV METHODS
    def generate_for_csv(self, input_data_source):
        triples_map = TriplesMap(self.ontology_uri,self.resource_uri)
        triples_map.add_logical_source(input_data_source,"ql:CSV")
        triples_map.add_subject_map("NAME","county")
        column_info = self.get_csv_column_info(input_data_source)
        for k,v in column_info.items():
            triples_map.add_predicate_object_map(k.replace(" ","_"),k,v)
        
        builder = RMLBuilder(self.ontology_uri,self.resource_uri,[triples_map])
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
    def generate_for_json(self, input_data_source):
        triples_map = TriplesMap(self.ontology_uri,self.resource_uri)
        triples_map.add_logical_source(input_data_source,"ql:CSV")
        triples_map.add_subject_map("NAME","county")
        column_info = self.get_csv_column_info(input_data_source)
        for k,v in column_info.items():
            triples_map.add_predicate_object_map(k.replace(" ","_"),k,v)
        
        builder = RMLBuilder(self.ontology_uri,self.resource_uri,[triples_map])
        print(builder.export_as_string())



generator = DefaultMappingGenerator("https://example.org/ontology/","https://example.org/resource/")
generator.generate_for_csv("/mnt/c/Users/Heyo/Desktop/ResearchTeam/ToposKG-Test-Sets/CSV/generic/census.csv")