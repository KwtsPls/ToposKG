import morph_kgc
from rdflib import Graph
import os

class RMLModule():
    def __init__(self):
        pass

    def generate_triples(self, mapping_file):
        config = """
        [DataSource1]
        mappings: /mnt/c/Users/Heyo/Desktop/ResearchTeam/ToposKG/toposkg_lib/toposkg/converter/rml/{}
        """.format(mapping_file)

        # Generate RDF using RDFLib
        g_rdflib = morph_kgc.materialize(config)
        
        return g_rdflib