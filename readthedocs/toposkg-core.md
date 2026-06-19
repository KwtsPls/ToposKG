# ToposKG-core

`ToposKG-core` contains the main library logic used to configure and execute the RDF generation pipeline.

This page documents the expected core concepts and parameters.

The core functionality of toposkg-lib is to construct custom geospatial knowledge graphs based on the ToposKG knowledge graph.

## `KnowledgeGraphBlueprint` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L27-L167">[source]</a>

The most basic "building block" of the Topos framework. It is responsible for collecting, managing and finally building the desired geospatial knowledge graph.


```python
KnowledgeGraphBlueprint(
    output_dir: str,
    sources_paths: List[str],
    name: str = "ToposKG.nt",
    materialization_pairs = [],
    translation_targets = []
)
```

A blueprint describing how a ToposKG knowledge graph should be constructed. It stores the output location, the selected RDF source files, and optional post-processing operations such as materialization and translation.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `output_dir` | `str` | required | Directory where the constructed knowledge graph will be written. |
| `sources_paths` | `List[str]` | required | List of source files or directories that should be included in the generated knowledge graph. |
| `name` | `str` | `"ToposKG.nt"` | Name of the output N-Triples file. |
| `linking_pairs` | `list` | `[]` | Pairs used for entity-linking operations. Currently stored in the blueprint, but not actively used by `construct()`. |
| `materialization_pairs` | `list` | `[]` | Pairs of source files for which geospatial materialization should be performed. |
| `translation_targets` | `list` | `[]` | Translation configuration, where each entry is expected to contain a source path and a list of predicates to translate. |

### Methods

#### `construct(validate=True, debug=False)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L36-L167">[source]</a>

```python
construct(validate: bool = True, debug: bool = False) -> str
```

Constructs the knowledge graph described by the blueprint.

The method concatenates selected RDF sources, optionally validates and serializes them as N-Triples, performs materialization over configured source pairs, and applies translation over configured predicate targets.

##### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `validate` | `bool` | `True` | If `True`, each source file is parsed with `rdflib` and serialized to N-Triples before being written. If `False` and the file already ends in `.nt`, the file is read directly. |
| `debug` | `bool` | `False` | Enables additional debug output during parsing, loading, placeholder replacement, and translation. |

##### Returns

| Type | Description |
|---|---|
| `str` | A success message containing the generated output path. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `output_dir` does not exist. |
| `ValueError` | Raised if one of the configured source paths does not exist. |
| `ValueError` | Raised if a non-local filesystem source is used during construction. |

##### Example

```python
blueprint = KnowledgeGraphBlueprint(
    output_dir="./output",
    sources_paths=["./data/greece.nt"],
    name="Greece.nt",
)

blueprint.construct(validate=False)
```



## `KnowledgeGraphBlueprintBuilder` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L170-L317">[source]</a>



```python
class KnowledgeGraphBlueprintBuilder()
```

Builder class for incrementally configuring and creating a `KnowledgeGraphBlueprint`.

This is the main convenience interface for users who want to select source files, configure output options, and create a knowledge graph construction blueprint without manually passing all parameters to `KnowledgeGraphBlueprint`.

### Methods

#### `set_name(name)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L179-L180">[source]</a>

```python
set_name(name) -> None
```

Sets the output file name for the generated knowledge graph.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `name` | `str` | Output file name, for example `"Greece.nt"`. |

---

#### `set_output_dir(output_dir)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L182-L185">[source]</a>

```python
set_output_dir(output_dir: str) -> None
```

Sets the directory where the generated knowledge graph should be written.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `output_dir` | `str` | Output directory path. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `output_dir` is not a string. |

---

#### `build()` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L191-L196">[source]</a>

```python
build() -> KnowledgeGraphBlueprint
```

Creates a `KnowledgeGraphBlueprint` from the current builder configuration.

##### Returns

| Type | Description |
|---|---|
| `KnowledgeGraphBlueprint` | A configured blueprint object. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if required fields are missing. Required fields are `output_dir` and `sources_paths`. |

---

#### `set_sources_path(sources_path)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L202-L205">[source]</a>

```python
set_sources_path(sources_path: list) -> None
```

Replaces the current source path collection with the given list.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `sources_path` | `list` | List of source file or directory paths. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `sources_path` is not a list. |

---

#### `add_source_path(source_path)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L207-L212">[source]</a>

```python
add_source_path(source_path: str) -> None
```

Adds a single source path to the builder.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `source_path` | `str` | Path to an RDF source file or directory. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `source_path` is not a string. |

---

#### `add_source_paths_with_strings(source_paths, substrings)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L214-L233">[source]</a>

```python
add_source_paths_with_strings(
    source_paths: list,
    substrings: List[str] | str,
) -> None
```

Adds source paths that contain all requested substrings and point to `.nt` files.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `source_paths` | `list` | Candidate source paths to filter. |
| `substrings` | `List[str] \| str` | Required substring or list of substrings. A path is added only if it contains all requested substrings. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `source_paths` is not a list of strings. |
| `ValueError` | Raised if any individual source path is not a string. |

##### Example

```python
builder.add_source_paths_with_strings(
    sources_manager.get_source_paths(),
    ["Greece", "OSM"],
)
```

---

#### `add_source_paths_with_regex(source_paths, regex_pattern)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L235-L245">[source]</a>

```python
add_source_paths_with_regex(
    source_paths: list,
    regex_pattern: str,
) -> None
```

Adds source paths that match a regular expression.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `source_paths` | `list` | Candidate source paths to filter. |
| `regex_pattern` | `str` | Regular expression used to select source paths. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `source_paths` is not a list of strings. |
| `ValueError` | Raised if any individual source path is not a string. |

##### Example

```python
builder.add_source_paths_with_regex(
    sources_manager.get_source_paths(),
    r"(?i).*Greece_(?!\d).*\.nt",
)
```

---

#### `remove_source_path(source_path)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L247-L251">[source]</a>

```python
remove_source_path(source_path: str) -> None
```

Removes a source path from the builder, if source paths have already been configured.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `source_path` | `str` | Source path to remove. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `source_path` is not a string. |

---

#### `clear_source_paths()` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L253-L260">[source]</a>

```python
clear_source_paths() -> None
```

Clears all configured source paths and resets linking pairs, materialization pairs, and translation targets.

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if no source paths have been configured. |

---

#### `print_source_paths()` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L262-L268">[source]</a>

```python
print_source_paths() -> None
```

Prints the currently configured source paths.

---

#### `set_linking_pairs(linking_pairs)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L274-L277">[source]</a>

```python
set_linking_pairs(linking_pairs: list) -> None
```

Sets the entity-linking pair configuration.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `linking_pairs` | `list` | Entity-linking pairs. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `linking_pairs` is not a list. |

---

#### `set_materialization_pairs(materialization_pairs)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L283-L286">[source]</a>

```python
set_materialization_pairs(materialization_pairs: list) -> None
```

Sets all geospatial materialization pairs.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `materialization_pairs` | `list` | List of source-path pairs used for geospatial materialization. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `materialization_pairs` is not a list. |

---

#### `add_materialization_pair(materialization_pair)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L288-L297">[source]</a>

```python
add_materialization_pair(materialization_pair: tuple) -> None
```

Adds a single pair of source paths for geospatial materialization.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `materialization_pair` | `tuple` | Tuple of two source paths. Both paths must already exist in the configured `sources_paths`. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `materialization_pair` is not a tuple of length two. |
| `ValueError` | Raised if the first element is not one of the configured source paths. |
| `ValueError` | Raised if the second element is not one of the configured source paths. |

##### Example

```python
builder.add_materialization_pair((source_a, source_b))
```

---

#### `set_translation_targets(translation_targets)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L303-L306">[source]</a>

```python
set_translation_targets(translation_targets: list) -> None
```

Sets all translation targets.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `translation_targets` | `list` | List of translation target configurations. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `translation_targets` is not a list. |

---

#### `add_translation_target(translation_target)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L308-L317">[source]</a>

```python
add_translation_target(translation_target: tuple) -> None
```

Adds a translation target.

Each translation target is expected to be a tuple whose first element is a source path and whose second element is a list of predicates to translate.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `translation_target` | `tuple` | Tuple of the form `(source_path, predicates_list)`. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `translation_target` is not a tuple of length two. |
| `ValueError` | Raised if the first element is not a string. |
| `ValueError` | Raised if the second element is not a list. |

##### Example

```python
builder.add_translation_target((
    "./data/greece.nt",
    ["<http://example.org/hasName>"],
))
```

---
---

## `KnowledgeGraphDataSource` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L320-L343">[source]</a>

```python
class KnowledgeGraphDataSource(
    path: str,
    metadata: Metadata,
)
```

Represents a single available ToposKG data source.

A data source can represent either a file or a directory. Directory-like sources may contain child `KnowledgeGraphDataSource` objects, allowing the available sources to be represented as a tree.

### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `path` | `str` | Path to the represented source file or directory. |
| `metadata` | `Metadata` | Metadata object associated with the source. May be `None` if no metadata file is available. |

### Attributes

| Attribute | Type | Description |
|---|---:|---|
| `name` | `str` | Basename of the source path. |
| `path` | `str` | Full source path. |
| `metadata` | `Metadata` | Loaded metadata for the source, or `None`. |
| `children` | `list` | Child data sources. |

### Methods

#### `print(indent=0)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L327-L332">[source]</a>

```python
print(indent: int = 0) -> None
```

Prints the data source and its children as an indented tree.

##### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `indent` | `int` | `0` | Number of indentation levels used when printing the current source. |

---

## `KnowledgeGraphSourcesManager` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L346-L532">[source]</a>

```python
class KnowledgeGraphSourcesManager(
    sources_repositories: str = "http://localhost:10001",
    sources_cache: str = "~/.toposkg/sources_cache",
)
```

Manages the available ToposKG source repositories and the local source cache.

The manager can download source files from a configured repository, create placeholders for sources that are not downloaded yet, load metadata, and expose sources either as a tree or as a flat list of paths.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `sources_repositories` | `str` | `"http://localhost:10001"` | Base URL of the source repository service. |
| `sources_cache` | `str` | `"~/.toposkg/sources_cache"` | Local directory where source files or placeholders are stored. |

### Methods

#### `add_data_sources_from_repository(sources_repository)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L461-L495">[source]</a>

```python
add_data_sources_from_repository(
    sources_repository: str,
) -> KnowledgeGraphDataSource
```

Loads source information from a repository directory and returns the root data source.

The method recursively traverses files and directories, skips metadata directories, loads metadata when available, and represents the result as a tree of `KnowledgeGraphDataSource` objects.

##### Parameters

| Parameter | Type | Description |
|---|---:|---|
| `sources_repository` | `str` | Path or filesystem URL of the source repository. |

##### Returns

| Type | Description |
|---|---|
| `KnowledgeGraphDataSource` | Root data source loaded from the repository. |

##### Raises

| Exception | Condition |
|---|---|
| `ValueError` | Raised if `sources_repository` is not a directory. |

---

#### `get_sources_as_tree()` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L497-L498">[source]</a>

```python
get_sources_as_tree() -> list
```

Returns the available data sources as a tree.

##### Returns

| Type | Description |
|---|---|
| `list` | List of root `KnowledgeGraphDataSource` objects. |

---

#### `get_sources_as_list(data_sources=None)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L500-L509">[source]</a>

```python
get_sources_as_list(data_sources=None) -> list
```

Flattens a source tree into a list.

##### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `data_sources` | `list \| None` | `None` | Source tree to flatten. If `None`, the manager's current `data_sources` are used. |

##### Returns

| Type | Description |
|---|---|
| `list` | Flat list of `KnowledgeGraphDataSource` objects. |

---

#### `get_source_paths()` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L511-L513">[source]</a>

```python
get_source_paths() -> list
```

Returns the paths of all available sources.

##### Returns

| Type | Description |
|---|---|
| `list` | List of source paths. |

---

#### `print_available_data_sources(tree=True, filter=None)` <a href="https://github.com/KwtsPls/ToposKG/blob/main/toposkg_lib/toposkg/toposkg_lib_core.py#L515-L532">[source]</a>

```python
print_available_data_sources(
    tree: bool = True,
    filter = None,
) -> None
```

Prints the available data sources.

The sources can be printed either as a tree or as a flat list. The optional `filter` argument restricts the printed sources to paths that contain the provided substring.

##### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `tree` | `bool` | `True` | If `True`, print sources as a tree. If `False`, print a flat list of source paths. |
| `filter` | `str \| None` | `None` | Optional substring used to filter displayed source paths. |

##### Example

```python
sources_manager = KnowledgeGraphSourcesManager(
    sources_repositories="https://toposkg.di.uoa.gr",
)

sources_manager.print_available_data_sources(
    tree=False,
    filter="Greece",
)
```

---

## End-to-end example

```python
sources_manager = KnowledgeGraphSourcesManager(
    sources_repositories="https://toposkg.di.uoa.gr",
)

sources_manager.print_available_data_sources(tree=False, filter="Greece")

builder = KnowledgeGraphBlueprintBuilder()
builder.add_source_paths_with_strings(
    sources_manager.get_source_paths(),
    ["Greece", "OSM"],
)
builder.set_output_dir("./output")
builder.set_name("Greece.nt")

blueprint = builder.build()
blueprint.construct(validate=False)
```

## End-to-end example with materialization and translation

More details on the materialization and translation pipelines can be found in our [website](https://toposkg.di.uoa.gr/)

```python
from toposkg.toposkg_lib_core import (
    KnowledgeGraphBlueprintBuilder,
    KnowledgeGraphSourcesManager
)

sources_manager = KnowledgeGraphSourcesManager(
    sources_repositories='https://toposkg.di.uoa.gr'
)


sources_manager.print_available_data_sources(
    tree=False,
    filter="Greece"
)

builder = KnowledgeGraphBlueprintBuilder()

builder.set_name("ToposKG.nt")
builder.set_output_dir("/content/")

builder.add_source_path(
"/root/.toposkg/sources_cache/toposkg/GAUL/countries/Greece/Greece_all.nt"
)

builder.add_source_path(
"/root/.toposkg/sources_cache/toposkg/OSM/forests/Greece/greece_forest.nt"
)

builder.add_translation_target(
(
 "/root/.toposkg/sources_cache/toposkg/OSM/countries/Greece/Greece_1.nt",
 ["<http://toposkg.di.uoa.gr/ontology/hasName>"]
)
)

mat_candidates = [("/root/.toposkg/sources_cache/toposkg/GAUL/countries/Greece/Greece_all.nt",
"/root/.toposkg/sources_cache/toposkg/OSM/forests/Greece/greece_forest.nt")]

builder.set_materialization_pairs(mat_candidates)



blueprint = builder.build()
blueprint.construct(validate=False)
```
