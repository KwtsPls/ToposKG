from toposkg.converter.toposkg_lib_converter import GenericConverter
import csv
import os
import hashlib

class CSVConverter(GenericConverter):
    def __init__(self, input_file, out_file, delimeter=",", ontology_uri="https://example.org/ontology/", resource_uri="https://example.org/resource/"):
        self.input_file = input_file
        self.out_file = out_file
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        self.delimeter = delimeter
        #internal data
        self.triples = []
        self.id_count = 0
        self.column_as_key = False

    def parse(self, id_columns=[], type_as_key=False):
        with open(self.input_file, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f,delimiter=self.delimeter)
            for row in reader:
                id = self.get_id(row,id_columns)
                for k,v in row.items():
                    if v is not None:
                        s = self.resource_uri + self.fast_hash8(self.input_file) + "_" + str(id)
                        p = self.ontology_uri + k
                        o = self.create_literal_string(v)
                        if o!=None:
                            self.triples += [(s, p, o)]

    def get_id(self, _dict, id_columns):
        id=None
        for i in id_columns:
            id =_dict.get(i, None)
            if id!=None:
                break
        if id is None:
            id = self.id_count
            self.id_count +=1
        return id
    
    def fast_hash8(self, s: str) -> bytes:
        h = hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()
        return h

    def create_literal_string(self, value):
        if value == None:
            return None
        elif isinstance(value, bool):
            return "\"" + str(value) + "\"^^<http://www.w3.org/2001/XMLSchema#boolean>"   
        elif isinstance(value, int):
            return "\"" + str(value) + "\"^^<http://www.w3.org/2001/XMLSchema#integer>"
        elif isinstance(value, float):
            return "\"" + str(value) + "\"^^<http://www.w3.org/2001/XMLSchema#double>"
        elif isinstance(value, str):
            return "\"" + value + "\"^^<http://www.w3.org/2001/XMLSchema#string>"  
        else:
            return "\"" + value + "\""
        
    def export(self):
        with open(self.out_file, "w") as f:
            for (s,p,o) in self.triples:
                if not o.startswith("\""):
                    o = "<" + o + ">"
                f.write("<{}> <{}> {} .\n".format(s,p,o))
