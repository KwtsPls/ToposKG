import os
import mimetypes
import json
import fsspec

from rdflib import Graph, RDF


class Metadata:
    def __init__(self):
        self.name = ""
        self.size = 0
        self.type = ""
        self.edges = 0
        self.nodes = 0
        self.predicates = 0
        self.average_degree = 0.0
        self.classes = 0
        self.country = None

    @classmethod
    def load_from_file(clss, filepath: str):
        with open(filepath, "r", encoding="utf-8") as meta_file:
            data = json.load(meta_file)
            instance = clss()
            instance.name = data.get("name", "")
            instance.size = data.get("size", 0)
            instance.type = data.get("type", "")
            instance.edges = data.get("edges", 0)
            instance.nodes = data.get("nodes", 0)
            instance.predicates = data.get("predicates", 0)
            instance.average_degree = data.get("average_degree", 0.0)
            instance.classes = data.get("classes", 0)
            instance.country = data.get("country", "") if "country" in data else None
            return instance

    def to_dict(self):
        return {
            "name": self.name,
            "size": self.size,
            "type": self.type,
            "edges": self.edges,
            "nodes": self.nodes,
            "predicates": self.predicates,
            "average_degree": self.average_degree,
            "classes": self.classes,
            "country": self.country,
        }
        
    @staticmethod
    def generate_metadata_for_file(filepath: str):
        """
        Generates metadata for a given file, including its name, size, and type.
        """
        fs, _ = fsspec.core.url_to_fs(filepath)
        is_local = fs.protocol in ["file", None] or fs.protocol == ('file', 'local')
        if not is_local:
            raise ValueError(f"Unsupported file system protocol: {fs.protocol}")

        name = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        mime_type, _ = mimetypes.guess_type(filepath)

        graph = Graph()
        graph.parse(filepath)

        # 1. Total number of edges (triples)
        num_edges = len(graph)

        # 2. Unique nodes (subjects and objects)
        nodes = set()
        for s, p, o in graph:
            nodes.add(s)
            nodes.add(o)
        num_nodes = len(nodes)

        # 3. Unique predicates (relationship types)
        unique_predicates = set(p for s, p, o in graph)
        num_unique_predicates = len(unique_predicates)

        # 4. Unique node types (rdf:type targets)
        unique_classes = set(o for s, p, o in graph.triples((None, RDF.type, None)))
        num_unique_classes = len(unique_classes)

        # 5. Average degree (assume undirected for simplicity)
        average_degree = (2 * num_edges) / num_nodes if num_nodes > 0 else 0

        return {
            "name": name,
            "size": size,
            "type": mime_type,
            "edges": num_edges,
            "nodes": num_nodes,
            "predicates": num_unique_predicates,
            "average_degree": average_degree,
            "classes": num_unique_classes,
        }

    @staticmethod
    def get_metadata_path_for_file(path: str):
        return f"{path.split('.')[0]}.kg_meta"