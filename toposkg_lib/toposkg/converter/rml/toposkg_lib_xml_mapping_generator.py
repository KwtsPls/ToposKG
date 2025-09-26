import hashlib
import os
import xml.etree.ElementTree as ET
from converter.rml import toposkg_lib_triples_map
from converter.rml import toposkg_lib_mapping_builder
from typing import Any

class XMLMappingGenerator():
    def __init__(self, ontology_uri, resource_uri):
        self.ontology_uri = ontology_uri
        self.resource_uri = resource_uri
        self.intermediate_file = None
        self.tree = None
        self.map_counter = 0
        self.maps = []

    def _load(self) -> ET.Element:
        """Load XML content from file."""
        try:
            tree = ET.parse(self.intermediate_file)
            return tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML in {self.intermediate_file}: {e}")

    def add_ids_to_xml(self, input_file: str):
        """Adds an incremental ID attribute to every XML element,
        stores parent ID in each child, and saves a new XML file with a hashed prefix."""

        # Compute 16-byte hash (blake2b for consistency)
        base_name = os.path.basename(input_file)
        file_hash = hashlib.blake2b(base_name.encode("utf-8"), digest_size=16).hexdigest()
        output_file = os.path.join(
            os.path.dirname(input_file),
            f"_{file_hash}{base_name}"
        )

        # Parse XML
        tree = ET.parse(input_file)
        root = tree.getroot()

        counter = {"id": 0}

        def walk(element, parent_id=None):
            current_id = counter["id"]
            element.set("_pyrml_mapper_generated_id", str(current_id))
            if parent_id is not None:
                element.set("_pyrml_mapper_parent_id", str(parent_id))
            counter["id"] += 1

            for child in element:
                walk(child, parent_id=current_id)

        walk(root)

        tree.write(output_file, encoding="utf-8", xml_declaration=True)
        return output_file

    def parse(self):
        """Naive method for converting XML files to .ntriple files."""
        def _walk(node):
            triplesMap = self.recursive_element_pass(node, None, None)
            return triplesMap

        triplesMap = _walk(self.tree)
        self.maps += [triplesMap]

    # Helper methods
    def recursive_element_pass(self, element: ET.Element, key: str, iterator: str = None):
        name = key
        if name is not None:
            name = f"{key}{self.map_counter}"
            self.map_counter += 1

        if iterator is None:
            iterator = "/" + element.tag  # XPath root
        else:
            iterator += "/" + element.tag

        triplesMap = toposkg_lib_triples_map.TriplesMap(self.ontology_uri, self.resource_uri, name)
        triplesMap.add_logical_source(self.intermediate_file, "ql:XPath", iterator)
        triplesMap.add_subject_map("@_pyrml_mapper_generated_id", element.tag)

        for child in element:
            child_key = child.tag
            if list(child):  # child has children
                childMap = self.recursive_element_pass(child, child_key, iterator)
                childMap.add_predicate_object_map_on_join(
                    child_key, triplesMap, "@_pyrml_mapper_parent_id", "@_pyrml_mapper_generated_id"
                )
                self.maps += [childMap]
            else:
                triplesMap.add_predicate_object_map(child_key, child_key, child.text)

        return triplesMap
    
    def generate_default_mapping(self, input_data_source):
        self.intermediate_file = self.add_ids_to_xml(input_data_source)
        self.tree = self._load()
        self.parse()
        self.maps.reverse()
        builder = toposkg_lib_mapping_builder.RMLBuilder(self.ontology_uri, self.resource_uri, self.maps)
        return builder.export_as_string()