import os
from converter.rml import toposkg_lib_triples_map

class RMLBuilder():
    def __init__(self, ontology_uri, resource_uri, maps=[]):
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        self.prefixes = self.load_prefixes()
        self.maps = maps

    def load_prefixes(self):
        return [
                "@prefix rr: <http://www.w3.org/ns/r2rml#>.",
                "@prefix  rml: <http://semweb.mmlab.be/ns/rml#> .",
                "@prefix ql: <http://semweb.mmlab.be/ns/ql#> .",
                "@prefix xsd: <http://www.w3.org/2001/XMLSchema#>.",
                "@base <http://geotriples.eu/base> .",
                "@prefix rrx: <http://www.w3.org/ns/r2rml-ext#>.",
                "@prefix rrxf: <http://www.w3.org/ns/r2rml-ext/functions/def/>.",
                "@prefix ogc: <http://www.opengis.net/ont/geosparql#>.",
                "@prefix schema: <http://schema.org/>.",
                "@prefix onto: <"+self.ontology_uri+">.",
                "@prefix resource: <"+self.resource_uri+">."
            ]
    
    def export_as_string(self):
        result = '\n'.join(self.prefixes) + "\n\n\n"
        for m in self.maps:
            result += m.export_as_string()
        return result