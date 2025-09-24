from toposkg_lib_converter import GenericConverter
from toposkg_lib_geojson_converter import GeoJSONConverter
import json
import os
import geopandas
import hashlib
from osgeo import ogr
from typing import Any, Dict

class KMLConverter(GenericConverter):
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
        kml_file = self.input_file
        # Output GeoJSON file
        geojson_file = self.fast_hash8(self.input_file)+".geojson"

        # Open the KML file
        driver = ogr.GetDriverByName('KML')
        dataset = driver.Open(kml_file)

        if not dataset:
            raise Exception("Could not open KML file.")

        # Get the first layer
        layer = dataset.GetLayer()

        # Create GeoJSON driver
        geojson_driver = ogr.GetDriverByName('GeoJSON')

        # Remove output file if it already exists
        geojson_driver.DeleteDataSource(geojson_file)

        # Create output
        out_ds = geojson_driver.CreateDataSource(geojson_file)
        out_layer = out_ds.CopyLayer(layer, layer.GetName())

        # Close and flush GDAL datasets
        out_ds = None
        dataset = None

        converter = GeoJSONConverter(self.fast_hash8(self.input_file)+".geojson", self.out_file, self.ontology_uri, self.resource_uri)
        converter.parse(id_fields,type_as_key)
        self.triples = converter.triples
        os.remove(self.fast_hash8(self.input_file)+".geojson")

    def fast_hash8(self, s: str) -> bytes:
        h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()
        return h