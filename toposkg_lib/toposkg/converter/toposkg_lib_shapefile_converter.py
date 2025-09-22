from toposkg_lib_converter import GenericConverter
from toposkg_lib_geojson_converter import GeoJSONConverter
import json
import os
import geopandas
import hashlib
import geojson
from shapely.geometry import shape
from typing import Any, Dict

class ShapefileConverter(GenericConverter):
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
        myshpfile = geopandas.read_file(self.input_file)
        myshpfile.to_file(self.fast_hash8(self.input_file)+".geojson", driver='GeoJSON')
        converter = GeoJSONConverter(self.fast_hash8(self.input_file)+".geojson", self.out_file, self.ontology_uri, self.resource_uri)
        converter.parse(id_fields,type_as_key)
        self.triples = converter.triples
        os.remove(self.fast_hash8(self.input_file)+".geojson")

    def fast_hash8(self, s: str) -> bytes:
        h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()
        return h
    
parser = ShapefileConverter("/mnt/c/Users/Heyo/Desktop/ResearchTeam/ToposKG-Test-Sets/Shapefile/generic/gadm41_ALB_0.shp",None)
parser.parse(id_fields=["id"])
for t in parser.triples:
    print(t)