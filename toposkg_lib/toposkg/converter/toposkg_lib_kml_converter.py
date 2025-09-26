from converter.toposkg_lib_converter import GenericConverter
from converter.toposkg_lib_geojson_converter import GeoJSONConverter
import json
import os
import geopandas as gpd
import pandas as pd
import fiona
import hashlib
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
        # Temporary GeoJSON file
        geojson_file = self.fast_hash8(self.input_file) + ".geojson"

        # List to hold GeoDataFrames for all layers
        gdfs = []

        # fiona requires a /vsizip/ path for KML zipped files or normal path for KML
        with fiona.Env():
            try:
                # Loop through all layers in the KML
                layers = fiona.listlayers(kml_file)
                for layer_name in layers:
                    gdf_layer = gpd.read_file(kml_file, layer=layer_name)
                    gdfs.append(gdf_layer)
            except Exception as e:
                raise Exception(f"Could not open KML file: {e}")

        # Concatenate all layers into a single GeoDataFrame
        if gdfs:
            combined_gdf = pd.concat(gdfs, ignore_index=True)
        else:
            raise Exception("No layers found in KML file.")

        # Save combined GeoDataFrame as GeoJSON
        combined_gdf.to_file(geojson_file, driver="GeoJSON")

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