from toposkg.converter.toposkg_lib_converter import GenericConverter
import json
import os
import hashlib
from typing import Any, Dict

class JSONConverter(GenericConverter):
    def __init__(self, input_file, out_file, ontology_uri="https://example.org/ontology/", resource_uri="https://example.org/resource/"):
        self.input_file = input_file
        self.out_file = out_file
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        #internal data
        self.data = self._load()
        self.triples = []
        self.id_count = 0
        self.dict_type_as_key = False


    def parse(self, id_fields=[], type_as_key=False):
        '''Naive method for converting JSON files to .ntriple files.
            Each line is handled as predicates for an id with a given entry'''
        def _walk(node, id_fields):
            if isinstance(node, dict):
                self.recursive_dict_pass(node,None,id_fields,None)
            elif isinstance(node, list):
                self.list_pass(node,None,id_fields,None)

        self.dict_type_as_key = type_as_key
        _walk(self.data, id_fields)

    def _load(self) -> Any:
        """Load JSON content from file."""
        try:
            with open(self.input_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {self.input_file}: {e}")


    def is_flat(self, node) -> bool:
        if isinstance(node, dict):
            for value in node.values():
                if not isinstance(value, dict) and not isinstance(value, list):
                    return False
            return True
        return False

    #Helper methods
    def recursive_dict_pass(self, _dict, key, id_fields, parent_entity=None):
        #Initial JSON file pass
        if parent_entity is None:
            if not self.is_flat(_dict):
                self.recursive_dict_pass(_dict,key,id_fields,"_")
                return

            for k,v in _dict.items():
                if isinstance(v,dict):
                    self.recursive_dict_pass(v, k, id_fields, "_")
                else:
                    self.list_pass(v, k, id_fields, "_")
            return

        if parent_entity == "_":
            id = self.get_id(_dict, id_fields)
            if key!=None:
                parent_entity = self.resource_uri + self.fast_hash8(self.input_file) + "_" + str(key) + str(id)
            else:
                parent_entity = self.resource_uri + self.fast_hash8(self.input_file) + "_" + str(id)

        for k,v in _dict.items():
            if k not in id_fields:
                if isinstance(v, dict):
                    cur_id = self.get_id(v, id_fields)
                    current_entity = self.resource_uri + self.fast_hash8(self.input_file) + "_" + str(k) + str(cur_id)
                    self.triples += [(parent_entity,self.ontology_uri+k,current_entity)]

                    if self.dict_type_as_key==True:
                        self.triples += [(current_entity, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", self.ontology_uri + k)]

                    self.recursive_dict_pass(v, k, id_fields, current_entity)
                elif isinstance(v, list):
                    self.list_pass(v, k, id_fields, parent_entity)
                else:
                    triple = self.parse_literal(v,k,parent_entity,key)
                    if triple != None:
                        self.triples += [triple]


    def list_pass(self, l, key, id_fields, parent_entity):
        if key==None and parent_entity==None:
            for v in l:
                if isinstance(v,dict):
                    self.recursive_dict_pass(v, None, id_fields, None)
                elif isinstance(v,list):
                    self.list_pass(v, None, id_fields, None)
            return
            
        for v in l:
            if isinstance(v, dict):
                if parent_entity!="_":
                    id = self.get_id(v, id_fields)
                    current_entity = self.resource_uri + self.fast_hash8(self.input_file) + "_" + str(key) + str(id)
                    self.triples += [(parent_entity, self.ontology_uri+key, current_entity)]

                    if self.dict_type_as_key==True:
                        self.triples += [(current_entity, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", self.ontology_uri + key)]

                    self.recursive_dict_pass(v, key, id_fields, current_entity)
                else:
                    self.recursive_dict_pass(v, key, id_fields, parent_entity)
            elif isinstance(v, list):
                self.list_pass(v, key, id_fields, parent_entity)
            else:
                o = self.create_literal_string(v)
                if o != None and parent_entity!=None and parent_entity!="_":
                    self.triples += [(parent_entity,self.ontology_uri+key,o)]


    def get_id(self, _dict, id_fields):
        id=None
        for i in id_fields:
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

    def parse_literal(self, value, key, id, upper_type=""):
        s = id
        p = self.ontology_uri + key
        o = self.create_literal_string(value)
        if o == None:
            return None
        return (s.replace(" ", "_"),p,o)
    
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
