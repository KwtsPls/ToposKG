from toposkg.converter.toposkg_lib_converter import GenericConverter
import xml.etree.ElementTree as ET
import hashlib

class XMLConverter(GenericConverter):
    def __init__(self, input_file, out_file, ontology_uri="https://example.org/ontology/", resource_uri="https://example.org/resource/"):
        self.input_file = input_file
        self.out_file = out_file
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        # internal data
        self.data = self._load()
        self.triples = []
        self.id_count = 0
        self.dict_type_as_key = False

    def _load(self):
        """Load XML content from file."""
        try:
            tree = ET.parse(self.input_file)
            return tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML in {self.input_file}: {e}")

    def parse(self, id_fields=[], type_as_key=False):
        """Naive XML to N-Triples converter."""
        self.dict_type_as_key = type_as_key
        self.recursive_xml_pass(self.data, None, id_fields, None)

    def recursive_xml_pass(self, element, parent_entity, id_fields, current_entity=None):
        """Recursive walk over XML tree."""
        # create subject for this element
        element_id = self.get_id(element, id_fields)
        current_entity = (
            self.resource_uri
            + self.fast_hash8(self.input_file)
            + "_"
            + element.tag
            + str(element_id)
        )

        if parent_entity is not None:
            self.triples.append((parent_entity, self.ontology_uri + element.tag, current_entity))

        # optional rdf:type triple
        if self.dict_type_as_key:
            self.triples.append(
                (
                    current_entity,
                    "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    self.ontology_uri + element.tag,
                )
            )

        # attributes as predicates
        for attr_key, attr_val in element.attrib.items():
            triple = self.parse_literal(attr_val, attr_key, current_entity)
            if triple:
                self.triples.append(triple)

        # text content as literal (if meaningful)
        if element.text and element.text.strip():
            triple = self.parse_literal(element.text.strip(), "value", current_entity)
            if triple:
                self.triples.append(triple)

        # recurse into children
        for child in element:
            self.recursive_xml_pass(child, current_entity, id_fields)

    def get_id(self, element, id_fields):
        id=None
        for i in id_fields:
            if i in element.attrib:
                return element.attrib[i]
        # fallback: incremental counter
        self.id_count += 1
        return self.id_count

    def fast_hash8(self, s: str) -> str:
        return hashlib.blake2b(s.encode("utf-8"), digest_size=8).hexdigest()

    def parse_literal(self, value, key, subject):
        s = subject
        p = self.ontology_uri + key
        o = self.create_literal_string(value)
        if o is None:
            return None
        return (s.replace(" ", "_"), p, o)

    def create_literal_string(self, value):
        if value is None:
            return None
        elif isinstance(value, bool):
            return "\"" + str(value).lower() + "\"^^<http://www.w3.org/2001/XMLSchema#boolean>"
        elif isinstance(value, int):
            return "\"" + str(value) + "\"^^<http://www.w3.org/2001/XMLSchema#integer>"
        elif isinstance(value, float):
            return "\"" + str(value) + "\"^^<http://www.w3.org/2001/XMLSchema#double>"
        else:
            return "\"" + str(value) + "\"^^<http://www.w3.org/2001/XMLSchema#string>"
        
    def export(self):
        with open(self.out_file, "w") as f:
            for (s,p,o) in self.triples:
                if not o.startswith("\""):
                    o = "<" + o + ">"
                f.write("<{}> <{}> {} .\n".format(s,p,o))