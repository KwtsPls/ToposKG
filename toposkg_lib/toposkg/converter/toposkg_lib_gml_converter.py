from toposkg.converter.toposkg_lib_converter import GenericConverter
from toposkg.converter.toposkg_lib_geojson_converter import GeoJSONConverter
import json
import os
import geopandas as gpd
import hashlib
import geojson
from shapely.geometry import shape
from typing import Any, Dict

class GMLConverter(GenericConverter):
    def __init__(self, input_file, out_file, ontology_uri="https://example.org/ontology/", resource_uri="https://example.org/resource/"):
        self.input_file = input_file
        self.out_file = out_file
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        #internal data
        self.triples = []
        self.id_count = 0
        self.dict_type_as_key = False

    def parse(self, id_fields=[], type_as_key=False):
        # Input GML file
        gml_file = self.input_file
        # Temporary GeoJSON file
        geojson_file = self.fast_hash8(self.input_file) + ".geojson"

        # Read the GML file using geopandas
        try:
            gdf = gpd.read_file(gml_file)
        except Exception as e:
            raise Exception(f"Could not open GML file: {e}")

        # Save as GeoJSON
        gdf.to_file(geojson_file, driver="GeoJSON")

        # Process with GeoJSONConverter
        converter = GeoJSONConverter(
            geojson_file, 
            self.out_file, 
            self.ontology_uri, 
            self.resource_uri
        )
        converter.parse(id_fields, type_as_key)
        self.triples = converter.triples

        # Remove temporary GeoJSON file
        os.remove(geojson_file)

    def fast_hash8(self, s: str) -> bytes:
        h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()
        return h
    
    def export(self):
        with open(self.out_file, "w") as f:
            for (s,p,o) in self.triples:
                if not o.startswith("\""):
                    o = "<" + o + ">"
                f.write("<{}> <{}> {} .\n".format(s,p,o))