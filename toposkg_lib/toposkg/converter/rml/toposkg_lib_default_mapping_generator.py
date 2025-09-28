import os
import pandas as pd
from rdflib import Graph
from toposkg.converter.rml import toposkg_lib_rml_module as m
from toposkg.converter.rml import toposkg_lib_mapping_builder as b
from toposkg.converter.rml import toposkg_lib_json_mapping_generator as json_generator
from toposkg.converter.rml import toposkg_lib_csv_mapping_generator as csv_generator
from toposkg.converter.rml import toposkg_lib_xml_mapping_generator as xml_generator
from toposkg.converter.rml import toposkg_lib_geojson_mapping_generator as geojson_generator

class DefaultMappingGenerator():
    def __init__(self, ontology_uri="https://example.org/ontology/", resource_uri="https://example.org/resource/"):
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri

    def generate_mappings(self, type, input_file, mapping_file):
        generator = None
        if type.lower()=="json":
            generator = json_generator.JSONMappingGenerator(self.ontology_uri, self.resource_uri)
        elif type.lower()=="csv":
            generator = csv_generator.CSVMappingGenerator(self.ontology_uri, self.resource_uri)
        elif type.lower()=="xml":
            generator = xml_generator.XMLMappingGenerator(self.ontology_uri, self.resource_uri)
        elif type.lower()=="geojson":
            generator = geojson_generator.GeoJSONMappingGenerator(self.ontology_uri, self.resource_uri)
        else:
            raise Exception("Non-supported type [{}]".format(type))
        
        #Generate mappings file
        generator.generate_default_mapping(input_file)
        builder = b.RMLBuilder(self.ontology_uri, self.resource_uri, generator.maps)
        with open(mapping_file, "w") as f:
            f.write(builder.export_as_string())

    def generate_triples(self, mapping_file, output_file):
        module = m.RMLModule()
        g_rdflib = module.generate_triples(mapping_file)
        try:
            g_rdflib.serialize(destination=output_file, format='nt')
            print(f"Graph successfully exported to {output_file}")
        except Exception as e:
            raise RuntimeError(f"Failed to export graph: {e}")

        

