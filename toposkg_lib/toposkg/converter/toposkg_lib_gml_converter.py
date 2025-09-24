from toposkg_lib_converter import GenericConverter
from toposkg_lib_geojson_converter import GeoJSONConverter
import json
import os
import geopandas
import hashlib
import geojson
from osgeo import ogr
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
        # Input KML file
        gml_file = self.input_file
        # Output GeoJSON file
        geojson_file = self.fast_hash8(self.input_file)+".geojson"

        # Open the KML file
        driver = ogr.GetDriverByName('GML')
        print(driver)
        dataset = driver.Open(gml_file)

        if not dataset:
            raise Exception("Could not open GML file.")

        # Create GeoJSON driver
        geojson_driver = ogr.GetDriverByName("GeoJSON")
        geojson_driver.DeleteDataSource(geojson_file)
        out_ds = geojson_driver.CreateDataSource(geojson_file)


        # Loop through all layers in the GML
        for i in range(dataset.GetLayerCount()):
            layer = dataset.GetLayerByIndex(i)
            out_ds.CopyLayer(layer, layer.GetName())

        # Close datasets (important!)
        out_ds = None
        dataset = None

        converter = GeoJSONConverter(self.fast_hash8(self.input_file)+".geojson", self.out_file, self.ontology_uri, self.resource_uri)
        converter.parse(id_fields,type_as_key)
        self.triples = converter.triples
        os.remove(self.fast_hash8(self.input_file)+".geojson")

    def fast_hash8(self, s: str) -> bytes:
        h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()
        return h