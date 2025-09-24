import morph_kgc
from rdflib import Graph
import os

class RMLModule():
    def __init__(self):
        pass

    def generate_triples(self):
        config = """
        [DataSource1]
        mappings: /mnt/c/Users/Heyo/Desktop/ResearchTeam/ToposKG/toposkg_lib/toposkg/converter/rml/out.ttl
        """

        # Generate RDF using RDFLib
        g_rdflib = morph_kgc.materialize(config)
        
        for s,p,o in g_rdflib:
            print(s,p,o)

module = RMLModule()
module.generate_triples()