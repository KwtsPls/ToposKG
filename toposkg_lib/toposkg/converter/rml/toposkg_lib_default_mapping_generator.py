import os
import pandas as pd
from toposkg_lib_triples_map import TriplesMap
from toposkg_lib_mapping_builder import RMLBuilder

class DefaultMappingGenerator():
    def __init__(self, ontology_uri, resource_uri):
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        pass
