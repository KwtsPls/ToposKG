import os
import fsspec
import requests
import subprocess

from rdflib import Graph
from typing import List
from rdflib import Graph
from rich.progress import Progress
from rich.console import Console

import importlib.util

if importlib.util.find_spec("toposkg") is not None:
    from toposkg.toposkg_lib_metadata import Metadata
    from toposkg.utils import get_relative_path
else:
    from toposkg_lib_metadata import Metadata
    from utils import get_relative_path


console = Console()
progress = None # the current progress bar instance, initialized later and used globally
task = None  # the current task in the progress bar, initialized later and used globally


class KnowledgeGraphBlueprint:
    def __init__(self, output_dir: str, sources_paths: List[str], name: str = "ToposKG.nt", linking_pairs = [], materialization_pairs = [], translation_targets = []):
        self.name = name
        self.output_dir = output_dir
        self.sources_paths = sources_paths
        self.linking_pairs = linking_pairs
        self.materialization_pairs = materialization_pairs
        self.translation_targets = translation_targets

    def construct(self, validate=True, debug=False):
        """
        Constructs the knowledge graph based on the provided blueprint.
        """
        if not os.path.isdir(self.output_dir):
            raise ValueError(f"Output directory {self.output_dir} does not exist.")

        output_path = os.path.join(self.output_dir, self.name)
        if os.path.exists(output_path):
            os.remove(output_path)
        output_file = open(output_path, 'w')
        
        console.print("Constructing knowledge graph...", style="bold yellow")

        #
        # concatenate all source files
        #
        def load_source_file_as_nt(file_path):
            if progress:
                progress.update(task, description=f"[cyan]Loading source file: {file_path}[/cyan]")
            if debug:
                print(f"Loading source file: {file_path}")

            fs, _ = fsspec.core.url_to_fs(file_path)
            is_local = fs.protocol in ["file", None] or fs.protocol == ('file', 'local')
            if not is_local:
                raise ValueError(f"Non-local construction is under development: {fs.protocol}")

            # Sanitize the file and convert to nt format
            if validate or not file_path.endswith('.nt'):
                g = Graph()
                if debug:
                    print(f"Parsing file: {file_path}")
                g.parse(file_path)
                nt_data = g.serialize(format='nt')
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    nt_data = f.read()
            return nt_data

        def write_file_to_output_file(file_path):
            nt_data = load_source_file_as_nt(file_path)
            if progress:
                progress.update(task, advance=1, description=f"[cyan]Writing source file: {file_path}[/cyan]")
            # Write to output file
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in nt_data.splitlines():
                    output_file.write(line + "\n")

        global progress, task
        if progress:
            progress.stop()
        progress = Progress()
        progress.start()
        
        for source_path in self.sources_paths:
            task = progress.add_task(f"[cyan]Processing {source_path}...", total=2)
            if not os.path.exists(source_path):
                raise ValueError(f"Source path {source_path} does not exist.")
            KnowledgeGraphSourcesManager._replace_placeholder_with_file(source_path, debug=debug)
            if os.path.isfile(source_path):
                write_file_to_output_file(source_path)
            else:
                for root, _, files in os.walk(source_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        KnowledgeGraphSourcesManager._replace_placeholder_with_file(file_path, debug=debug)
                        write_file_to_output_file(file_path)
            progress.update(task, advance=1, description=f"[green]Added source file: {source_path}[/green]")
        
        progress.stop()
        progress = None
        
        # materialization
        progress = Progress()
        progress.start()
        
        script_path = "./scripts/materialization.sh"
        for pair in self.materialization_pairs:
            task = progress.add_task(f"[cyan]Materializing pair {pair[0]} - {pair[1]}", total=2)
            try:
                result = subprocess.run(["bash", script_path, pair[0], pair[1], 'materialization'],
                            check=True,
                            capture_output=True,
                            text=True)
                # print("STDOUT:\n", result.stdout)
                # print("STDERR:\n", result.stderr)
                progress.update(task, advance=1, description=f"[green]Materialized pair {pair[0]} - {pair[1]}[/green]")
                write_file_to_output_file(get_relative_path('materialization_map.nt'))
                progress.update(task, advance=1, description=f"[green]Written materialization results for pair {pair[0]} - {pair[1]}[/green]")
                # Clean up the temporary files
                os.remove(get_relative_path('materialization_map.nt'))
                os.remove(get_relative_path('materialization.nt'))
            except subprocess.CalledProcessError as e:
                print("Script failed with return code:", e.returncode)
                print("Error output:\n", e.stderr)
                
        progress.stop()
        progress = None

        #
        # translation
        #
        if len(self.translation_targets) > 0:
            print("Translating...")
            if importlib.util.find_spec("toposkg") is not None:
                from toposkg.toposkg_lib_translate import ToposkgLibTranslator
            else:
                from toposkg_lib_translate import ToposkgLibTranslator

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

        console.print("Knowledge graph constructed successfully at " + output_path, style="bold green")
            
        return "Knowledge graph constructed successfully at " + output_path


class KnowledgeGraphBlueprintBuilder:
    
    def __init__(self):
        self._data = {}
        
    # -------------------------
    # ----- Build Options -----
    # -------------------------

    def set_name(self, name):
        self._data['name'] = name

    def set_output_dir(self, output_dir):
        if not isinstance(output_dir, str):
            raise ValueError("output_dir must be a string")
        self._data['output_dir'] = output_dir
        
    # -----------------
    # ----- Build -----
    # -----------------

    def build(self):
        required_keys = ['output_dir', 'sources_paths']
        missing = [k for k in required_keys if k not in self._data]
        if missing:
            raise ValueError(f"Missing fields: {missing}")
        return KnowledgeGraphBlueprint(**self._data)
    
    # -----------------------------
    # ----- Source Management -----
    # -----------------------------

    def set_sources_path(self, sources_path):
        if not isinstance(sources_path, list):
            raise ValueError("sources_path must be a list")
        self._data['sources_paths'] = sources_path

    def add_source_path(self, source_path):
        if not isinstance(source_path, str):
            raise ValueError("source_path must be a string")
        if 'sources_paths' not in self._data:
            self._data['sources_paths'] = set()
        self._data['sources_paths'].add(source_path)
    
    def add_source_paths_with_strings(self, source_paths, substrings: List[str]|str):
        if not isinstance(source_paths, List):
            raise ValueError("source_paths must be a list of strings")
        if isinstance(substrings, str):
            substrings = [substrings]
        if 'sources_paths' not in self._data:
            self._data['sources_paths'] = set()
        for source_path in source_paths:
            if not isinstance(source_path, str):
                raise ValueError("Each source_path must be a string")
            if ".nt" not in source_path:
                continue
            skip = False
            for substring in substrings:
                if substring not in source_path:
                    skip = True
                    break
            if skip:
                continue
            self._data['sources_paths'].add(source_path)
            
    def add_source_paths_with_regex(self, source_paths, regex_pattern: str):
        import re
        if not isinstance(source_paths, List):
            raise ValueError("source_paths must be a list of strings")
        if 'sources_paths' not in self._data:
            self._data['sources_paths'] = set()
        for source_path in source_paths:
            if not isinstance(source_path, str):
                raise ValueError("Each source_path must be a string")
            if re.search(regex_pattern, source_path):
                self._data['sources_paths'].add(source_path)

    def remove_source_path(self, source_path):
        if not isinstance(source_path, str):
            raise ValueError("source_path must be a string")
        if 'sources_paths' in self._data:
            self._data['sources_paths'].remove(source_path)
            
    def clear_source_paths(self):
        if 'sources_paths' in self._data:
            self._data['sources_paths'] = set()
            self.set_linking_pairs([])
            self.set_materialization_pairs([])
            self.set_translation_targets([])
        else:
            raise ValueError("No sources_paths to clear")
        
    def print_source_paths(self):
        if 'sources_paths' in self._data:
            print("Sources paths:")
            for path in sorted(self._data['sources_paths']):
                print(f"- {path}")
        else:
            console.print("No sources paths set.", style="yellow")
            
    # --------------------------
    # ----- Entity Linking -----
    # --------------------------

    def set_linking_pairs(self, linking_pairs):
        if not isinstance(linking_pairs, list):
            raise ValueError("linking_pairs must be a list")
        self._data['linking_pairs'] = linking_pairs
        
    # -----------------------------------
    # ----- Geospatial Interlinking -----
    # -----------------------------------

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
        
    # -----------------------
    # ----- Translation -----
    # -----------------------

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
    def __init__(self, sources_repositories='http://localhost:10001', sources_cache='~/.toposkg/sources_cache'):
        # TODO: Enable support for custom sources repositories
        # if not isinstance(sources_repositories, list):
        #     raise ValueError("sources_repositories must be a list")
        self.sources_repositories = sources_repositories
        self.data_sources = []
        self.sources_cache = sources_cache

        if not os.path.isdir(os.path.expanduser(sources_cache)):
            os.makedirs(os.path.expanduser(sources_cache))

        answer = input("Do you want to proceed with downloading the entire knowledge graph sources (100gb+)? Any previously downloaded sources will not be redownloaded. (y/n)")
        if answer.lower() != 'y':
            print("Skipping download of sources...")
            skip = True
        else:
            print("Downloading sources...")
            skip = False

        # Temporarily use sources_cache as a single repository. Download the entire KG.
        response = requests.get(f"{sources_repositories}/get_data_sources_list")
        # Parse and print JSON response
        if response.ok:
            data = response.json()
        else:
            data = []
            console.print(f"Request failed with status code {response.status_code}", style="yellow")
        for source in data:
            download_path = source.get("path", "")
            output_file = f"{os.path.expanduser(sources_cache)}/{download_path.split('static/data/')[-1]}"

            if not skip:
                if os.path.exists(output_file):
                    # print(f"File {output_file} already exists.")
                    self._replace_placeholder_with_file(output_file)
                else:
                    self._download_data_source(sources_repositories, download_path, output_file)
            else:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                if not os.path.exists(output_file):
                    # print(f"File {output_file} does not exist. Creating a placeholder.")
                    with open(output_file, "w") as file:
                        file.write(f"Placeholder\n{self.sources_repositories}\n{download_path}\n{output_file}")

        # Load KnowledgeGraphDataSource from the sources_cache
        fs, path_in_fs = fsspec.core.url_to_fs(sources_cache)
        if not fs.exists(sources_cache):
            raise ValueError(f"Source repository {sources_cache} does not exist.")
        print(f"Loading source information from {sources_cache}")
        data_source = self.add_data_sources_from_repository(sources_cache)
        self.data_sources.append(data_source)

        # TODO: Enable support for custom sources repositories
        # for sources_repository in self.sources_repositories:
        #     fs, path_in_fs = fsspec.core.url_to_fs(sources_repository)
        #     if not fs.exists(sources_repository):
        #         raise ValueError(f"Source repository {sources_repository} does not exist.")
        #     print(f"Adding sources from {sources_repository}")
        #     data_source = self.add_data_sources_from_repository(sources_repository)
        #     self.data_sources.append(data_source)

    @staticmethod
    def _download_data_source(repository: str, download_path: str, output_file: str):
        if progress:
            progress.update(task, description=f"[cyan]Downloading {download_path}...[/cyan]")
        url = f"{repository}/download_source?path={download_path}"
        response = requests.get(url)
        if response.ok:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, "wb") as file:
                file.write(response.content)
            if progress:
                progress.update(task, advance=1, description=f"[green]Downloaded {download_path} to {output_file}[/green]")
        else:
            console.print(f"Failed to download file. Status code: {response.status_code}", style="yellow")

    @staticmethod
    def _replace_placeholder_with_file(file_path: str, debug=False):
        """
        Replace the placeholder file with the actual file.
        Placeholder files are files that contain the text "Placeholder" in them.
        """
        if KnowledgeGraphSourcesManager._check_if_file_is_placeholder(file_path):
            if progress:
                progress.update(task, description=f"[yellow]Replacing placeholder file {file_path} with actual file...[/yellow]")
            if debug:
                print(f"Replacing placeholder file {file_path} with actual file.")
            with open(file_path, "r", encoding="utf-8") as file:
                lines = file.readlines()
                repository = lines[1].split("\n")[0]
                download_path = lines[2].split("\n")[0]
                output_file = lines[3].split("\n")[0]
            KnowledgeGraphSourcesManager._download_data_source(
                repository=repository,
                download_path=download_path,
                output_file=output_file
            )

    @staticmethod
    def _check_if_file_is_placeholder(file_path: str):
        """
        Check if the file is a placeholder file.
        Placeholder files are files that contain the text "Placeholder" in them.
        """
        if os.path.isdir(file_path):
            return False
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                first_line = file.readline().strip()
                return first_line == "Placeholder"
        except Exception as e:
            console.print(f"Error reading file {file_path}: {e}", style="red")
            return False

    def add_data_sources_from_repository(self, sources_repository: str):
        def add_items(parent_item, path):
            if "kg_meta" in path:
                return
            metadata_filepath = Metadata.get_metadata_path_for_file(path)
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
                            console.print(f"Unknown file type: {full_path}", style="red")
                except PermissionError:
                    console.print(f"Permission error: {full_path}", style="red")
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

    def print_available_data_sources(self, tree=True, filter=None):
        print("Available data sources:")
        if tree:
            sources = self.get_sources_as_tree()
            for source in sources:
                if filter is not None:
                    if filter not in source.path:
                        continue
                print(source.path + "/")
                for child in source.children:
                    child.print(1)
        else:
            sources = self.get_source_paths()
            for source in sources:
                if filter is not None:
                    if filter not in source:
                        continue
                print(source)


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
    # generate_metadata_recursive('PATH_TO_KG_SOURCES')

    sources_manager = KnowledgeGraphSourcesManager(sources_repositories='https://toposkg.di.uoa.gr',)
    sources_manager.print_available_data_sources(tree=False, filter="Greece")
    
    builder = KnowledgeGraphBlueprintBuilder()
    builder.add_source_paths_with_strings(sources_manager.get_source_paths(), ["Greece", "OSM"])
    builder.print_source_paths()
    
    builder.clear_source_paths()
    builder.add_source_paths_with_regex(sources_manager.get_source_paths(), r"(?i).*Greece_(?!\d).*\.nt")
    builder.add_materialization_pair(('/home/sergios/.toposkg/sources_cache/toposkg/OSM/pois/Greece/greece_poi.nt', '/home/sergios/.toposkg/sources_cache/toposkg/OSM/pois/Greece/greece_poi.nt'))
    builder.print_source_paths()
    
    builder.set_output_dir("/home/sergios/ToposKG/")
    
    # builder.build().construct(validate=False)
    
    # builder.clear_source_paths()
    # builder.add_source_path('/home/sergios/.toposkg/sources_cache/toposkg/GAUL/countries/Greece')
    # builder.print_source_paths()
    
    # builder.set_name("Greece_GAUL_dir.nt")
    
    # builder.build().construct(validate=False)
    
    builder.clear_source_paths()
    builder.add_source_path('/home/sergios/.toposkg/sources_cache/toposkg/GAUL/countries/United States of America/United States of America_1.nt')
    builder.print_source_paths()
    
    builder.set_name("USA.nt")
    
    builder.build().construct(validate=False)