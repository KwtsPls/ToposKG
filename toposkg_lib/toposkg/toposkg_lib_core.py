import os
import mimetypes
from rdflib import Graph, RDF, RDFS, OWL
import json
import fsspec
from typing import List
from rdflib import Graph


class KnowledgeGraphBlueprint:
    def __init__(self, output_dir: str, sources_paths: List[str], name: str = "ToposKG.nt", linking_pairs = [], materialization_pairs = [], translation_targets = []):
        self.name = name
        self.output_dir = output_dir
        self.sources_paths = sources_paths
        self.linking_pairs = linking_pairs
        self.materialization_pairs = materialization_pairs
        self.translation_targets = translation_targets

    def construct(self, debug=False):
        """
        Constructs the knowledge graph based on the provided blueprint.
        """
        if not os.path.isdir(self.output_dir):
            raise ValueError(f"Output directory {self.output_dir} does not exist.")

        output_path = os.path.join(self.output_dir, self.name)
        if os.path.exists(output_path):
            os.remove(output_path)
        output_file = open(output_path, 'w')

        print("Constructing knowledge graph...")

        #
        # concatenate all source files
        #
        def load_source_file_as_nt(file_path):
            if debug:
                print(f"Loading source file: {file_path}")

            fs, _ = fsspec.core.url_to_fs(file_path)
            is_local = fs.protocol in ["file", None] or fs.protocol == ('file', 'local')
            if not is_local:
                raise ValueError(f"Non-local construction is under development: {fs.protocol}")

            # Sanitize the file and convert to nt format
            g = Graph()
            if debug:
                print(f"Parsing file: {file_path}")
            g.parse(file_path)
            nt_data = g.serialize(format='nt')
            return nt_data

        def write_file_to_output_file(file_path):
            nt_data = load_source_file_as_nt(file_path)
            # Write to output file
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in nt_data.splitlines():
                    output_file.write(line + "\n")

        for source_path in self.sources_paths:
            if debug:
                print(f"Processing source path: {source_path}")
            if not os.path.exists(source_path):
                raise ValueError(f"Source path {source_path} does not exist.")
            if os.path.isfile(source_path):
                write_file_to_output_file(source_path)
            else:
                for root, _, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        write_file_to_output_file(file_path)

        # materialization
        for pair in self.materialization_pairs:
            pass

        #
        # translation
        #
        print("Translating...")
        if len(self.translation_targets) > 0:
            from toposkg.toposkg_lib_translate import ToposkgLibTranslator

            translator = ToposkgLibTranslator()

            for source_path, predicates_list in self.translation_targets:
                print("Translating predicates in source path: ", source_path)
                print("Predicates list: ", predicates_list)
                nt_data = load_source_file_as_nt(source_path)
                # Write to output file
                for line in nt_data.splitlines():
                    subject, predicate, object, dot = line.split(" ")[0], line.split(" ")[1], " ".join(
                        line.split(" ")[2:-1]), line.split(" ")[-1]
                    if predicate in predicates_list:
                        # Translate the object
                        translated_object = translator.translate(object)
                        if debug:
                            print(f"Translating {object} to {translated_object}")
                        output_file.write(f"{subject} {predicate} {translated_object} {dot}\n")

        output_file.close()

        print("Knowledge graph constructed successfully at ", output_path)


class KnowledgeGraphBlueprintBuilder:
    def __init__(self):
        self._data = {}

    def set_name(self, name):
        self._data['name'] = name

    def set_output_dir(self, output_dir):
        if not isinstance(output_dir, str):
            raise ValueError("output_dir must be a string")
        self._data['output_dir'] = output_dir

    def set_sources_path(self, sources_path):
        if not isinstance(sources_path, list):
            raise ValueError("sources_path must be a list")
        self._data['sources_paths'] = sources_path

    def add_source_path(self, source_path):
        if not isinstance(source_path, str):
            raise ValueError("source_path must be a string")
        if 'sources_paths' not in self._data:
            self._data['sources_paths'] = []
        self._data['sources_paths'].append(source_path)

    def set_linking_pairs(self, linking_pairs):
        if not isinstance(linking_pairs, list):
            raise ValueError("linking_pairs must be a list")
        self._data['linking_pairs'] = linking_pairs

    def set_materialization_pairs(self, materialization_pairs):
        if not isinstance(materialization_pairs, list):
            raise ValueError("materialization_pairs must be a list")
        self._data['materialization_pairs'] = materialization_pairs

    def add_materialization_pair(self, materialization_pair):
        if not isinstance(materialization_pair, tuple) or len(materialization_pair) != 2:
            raise ValueError("Each materialization pair must be a tuple of two elements")
        if not materialization_pair[0] in self._data['sources_paths']:
            raise ValueError("The first element must be one of the sources_paths")
        if not materialization_pair[1] in self._data['sources_paths']:
            raise ValueError("The second element must be one of the sources_paths")
        if 'materialization_pairs' not in self._data:
            self._data['materialization_pairs'] = []
        self._data['materialization_pairs'].append(materialization_pair)

    def set_translation_targets(self, translation_targets):
        if not isinstance(translation_targets, list):
            raise ValueError("translation_targets must be a list")
        self._data['translation_targets'] = translation_targets

    def add_translation_target(self, translation_target):
        if not isinstance(translation_target, tuple) or len(translation_target) != 2:
            raise ValueError("Each translation target must be a tuple of two elements")
        if not isinstance(translation_target[0], str):
            raise ValueError("The first element of each translation target must be a string")
        if not isinstance(translation_target[1], list):
            raise ValueError("The second element of each translation target must be a list")
        if 'translation_targets' not in self._data:
            self._data['translation_targets'] = []
        self._data['translation_targets'].append(translation_target)

    def build(self):
        required_keys = ['output_dir', 'sources_paths']
        missing = [k for k in required_keys if k not in self._data]
        if missing:
            raise ValueError(f"Missing fields: {missing}")
        return KnowledgeGraphBlueprint(**self._data)


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


class KnowledgeGraphDataSource:
    def __init__(self, path: str, metadata: Metadata):
        self.name = os.path.basename(path)
        self.path = path
        self.metadata = metadata
        self.children = []

    def print(self, indent=0):
        indents = "  " * indent
        dir_suffix = "/" if os.path.isdir(self.path) else ""
        print(indents + self.name + dir_suffix)
        for child in self.children:
            child.print(indent + 1)

    def __repr__(self):
        return f"KnowledgeGraphDataSource(name={self.name}, path={self.path})"

    def __eq__(self, other):
        if not isinstance(other, KnowledgeGraphDataSource):
            return NotImplemented
        return self.path == other.path

    def __hash__(self):
        return hash(self.path)


class KnowledgeGraphSourcesManager:
    def __init__(self, sources_repositories):
        if not isinstance(sources_repositories, list):
            raise ValueError("sources_repositories must be a list")
        self.sources_repositories = sources_repositories
        self.data_sources = []

        for sources_repository in self.sources_repositories:
            fs, path_in_fs = fsspec.core.url_to_fs(sources_repository)
            if not fs.exists(sources_repository):
                raise ValueError(f"Source repository {sources_repository} does not exist.")
            print(f"Adding sources from {sources_repository}")
            data_source = self.add_data_sources_from_repository(sources_repository)
            self.data_sources.append(data_source)

    def add_data_sources_from_repository(self, sources_repository: str):
        def add_items(parent_item, path):
            if "kg_meta" in path:
                return
            metadata_filepath = get_metadata_path_for_file(path)
            if fs.exists(metadata_filepath):
                metadata = Metadata.load_from_file(metadata_filepath)
            else:
                metadata = None
            item = KnowledgeGraphDataSource(path, metadata)
            parent_item.children.append(item)

            if not ".zip" in path and fs.isdir(path): # We treat .zip files as files, not directories
                try:
                    for full_path in sorted(fs.ls(path, detail=False)):
                        if full_path == path or full_path[:-1] == path or "?C" in full_path:
                            continue
                        if ".zip" in full_path or fs.isfile(full_path):
                            add_items(item, full_path)
                        elif fs.isdir(full_path):
                            add_items(item, full_path)
                        else:
                            print(f"Unknown file type: {full_path}")
                except PermissionError:
                    print(f"Permission error: {full_path}")
                    pass  # Skip folders we can't access

        fs, path_in_fs = fsspec.core.url_to_fs(sources_repository)

        if not fs.isdir(path_in_fs):
            raise ValueError(f"Source repository {sources_repository} is not a directory.")

        data_source = KnowledgeGraphDataSource("placeholder/placeholder", None)
        add_items(data_source, path_in_fs)
        return data_source.children[0]

    def get_sources_as_tree(self):
        return self.data_sources

    def get_sources_as_list(self, data_sources=None):
        if data_sources is None:
            data_sources = self.data_sources

        sources = []
        for source in data_sources:
            sources.append(source)
            children_sources = self.get_sources_as_list(source.children)
            sources.extend(children_sources)
        return sources

    def get_source_paths(self):
        paths = [source.path for source in self.get_sources_as_list()]
        return paths

    def print_available_data_sources(self):
        sources = self.get_sources_as_tree()
        for source in sources:
            print(source.path + "/")
            for child in source.children:
                child.print(1)


def generate_metadata_for_file(filepath: str):
    """
    Generates metadata for a given file, including its name, size, and type.
    """
    fs, _ = fsspec.core.url_to_fs(filepath)
    is_local = fs.protocol in ["file", None]
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


def get_metadata_path_for_file(path: str):
    return f"{path.split('.')[0]}.kg_meta"


if __name__ == "__main__":
    # def generate_metadata_recursive(path):
    #     if os.path.isdir(path):
    #         try:
    #             for name in sorted(os.listdir(path)):
    #                 full_path = os.path.join(path, name)
    #                 generate_metadata_recursive(full_path)
    #         except PermissionError:
    #             pass  # Skip folders we can't access
    #     elif os.path.isfile(path):
    #         print("Generating metadata for {}".format(path))
    #         metadata = generate_metadata_for_file(path)
    #         with open(get_metadata_path_for_file(path), "w", encoding="utf-8") as meta_file:
    #             json.dump(metadata, meta_file, indent=4)
    #
    # generate_metadata_recursive('/home/sergios/kg_sources/')

    sources = KnowledgeGraphSourcesManager(['/home/sergios/kg_sources/', 'https://yago2geo.di.uoa.gr/data'])
    sources.print_available_data_sources()
    #
    # for path in data_sources_paths:
    #     print(path)

