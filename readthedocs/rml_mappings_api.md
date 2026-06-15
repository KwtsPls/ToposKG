# RML Mapping API

This page documents the public, user-facing classes for generating and executing [RML](https://rml.io/specs/rml/) mappings. These classes are useful when you want a reusable mapping file instead of directly converting input data to triples.


The most convenient entry point is `DefaultMappingGenerator`:

```python
generator = DefaultMappingGenerator()
generator.generate_mappings("geojson", "data/pois.geojson", "mappings/pois.ttl")
generator.generate_triples("mappings/pois.ttl", "out/pois.nt")
```

---

## `DefaultMappingGenerator` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_default_mapping_generator.py#L11)

```python
class DefaultMappingGenerator(
    ontology_uri="https://example.org/ontology/",
    resource_uri="https://example.org/resource/",
)
```

High-level utility for generating default RML mappings and materializing triples from those mappings. This is the class most users should start with.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `ontology_uri` | `str` | `"https://example.org/ontology/"` | URI prefix used for generated predicates/classes in the mapping. |
| `resource_uri` | `str` | `"https://example.org/resource/"` | URI prefix used for generated subject/object resources. |

### Methods

#### `DefaultMappingGenerator.generate_mappings(type, input_file, mapping_file)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_default_mapping_generator.py#L16)

```python
generate_mappings(type, input_file, mapping_file)
```

Generate a default RML mapping file for the selected input type.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `type` | `str` | required | Input format. Supported values are `"json"`, `"csv"`, `"xml"`, and `"geojson"`. |
| `input_file` | `str` | required | Path to the input data source. |
| `mapping_file` | `str` | required | Path where the generated RML mapping file will be written. |

**Raises:** `Exception` if `type` is not supported.

#### `DefaultMappingGenerator.generate_triples(mapping_file, output_file)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_default_mapping_generator.py#L35)

```python
generate_triples(mapping_file, output_file)
```

Materialize triples from an RML mapping and serialize the result as N-Triples.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `mapping_file` | `str` | required | Path to an RML mapping file. |
| `output_file` | `str` | required | Path where the generated N-Triples file will be written. |

**Raises:** `RuntimeError` if graph serialization fails.

### Example

```python
from toposkg.converter.rml.toposkg_lib_default_mapping_generator import DefaultMappingGenerator

generator = DefaultMappingGenerator(
    ontology_uri="https://example.org/ontology/",
    resource_uri="https://example.org/resource/",
)
generator.generate_mappings("csv", "data/places.csv", "mappings/places.ttl")
generator.generate_triples("mappings/places.ttl", "out/places.nt")
```

---

## `CSVMappingGenerator` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_csv_mapping_generator.py#L7)

```python
class CSVMappingGenerator(ontology_uri, resource_uri)
```

Format-specific default RML mapping generator for CSV files. It creates an intermediate CSV file with a generated ID column and builds a single `TriplesMap` over the CSV columns.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `ontology_uri` | `str` | required | URI prefix used for generated predicates/classes. |
| `resource_uri` | `str` | required | URI prefix used for generated resources. |

### Methods

#### `CSVMappingGenerator.generate_default_mapping(input_data_source)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_csv_mapping_generator.py#L69)

```python
generate_default_mapping(input_data_source)
```

Generate default CSV mapping objects and store them in `self.maps`.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `input_data_source` | `str` | required | Path to the input CSV file. |

**Note:** Unlike the JSON/XML/GeoJSON mapping generators, this implementation populates `self.maps` but does not return the mapping string directly. Use `RMLBuilder` to export `self.maps`.

---

## `JSONMappingGenerator` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_json_mapping_generator.py#L8)

```python
class JSONMappingGenerator(ontology_uri, resource_uri)
```

Format-specific default RML mapping generator for JSON files. It creates an intermediate JSON file with generated IDs and parent IDs, recursively builds `TriplesMap` objects, and exports them as an RML mapping string.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `ontology_uri` | `str` | required | URI prefix used for generated predicates/classes. |
| `resource_uri` | `str` | required | URI prefix used for generated resources. |

### Methods

#### `JSONMappingGenerator.generate_default_mapping(input_data_source)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_json_mapping_generator.py#L167)

```python
generate_default_mapping(input_data_source)
```

Generate and return a default RML mapping string for a JSON file.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `input_data_source` | `str` | required | Path to the input JSON file. |

**Returns:** `str` containing the generated RML mapping.

---

## `GeoJSONMappingGenerator` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_geojson_mapping_generator.py#L9)

```python
class GeoJSONMappingGenerator(ontology_uri, resource_uri)
```

Format-specific default RML mapping generator for GeoJSON files. It augments the input with generated IDs, transforms geometry dictionaries to WKT where possible, and creates RML mappings over the resulting JSON structure.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `ontology_uri` | `str` | required | URI prefix used for generated predicates/classes. |
| `resource_uri` | `str` | required | URI prefix used for generated resources. |

### Methods

#### `GeoJSONMappingGenerator.generate_default_mapping(input_data_source)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_geojson_mapping_generator.py#L198)

```python
generate_default_mapping(input_data_source)
```

Generate and return a default RML mapping string for a GeoJSON file.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `input_data_source` | `str` | required | Path to the input GeoJSON file. |

**Returns:** `str` containing the generated RML mapping.

---

## `XMLMappingGenerator` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_xml_mapping_generator.py#L8)

```python
class XMLMappingGenerator(ontology_uri, resource_uri)
```

Format-specific default RML mapping generator for XML files. It creates an intermediate XML file with generated ID and parent ID attributes, then builds XPath-based RML `TriplesMap` objects.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `ontology_uri` | `str` | required | URI prefix used for generated predicates/classes. |
| `resource_uri` | `str` | required | URI prefix used for generated resources. |

### Methods

#### `XMLMappingGenerator.generate_default_mapping(input_data_source)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_xml_mapping_generator.py#L98)

```python
generate_default_mapping(input_data_source)
```

Generate and return a default RML mapping string for an XML file.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `input_data_source` | `str` | required | Path to the input XML file. |

**Returns:** `str` containing the generated RML mapping.

---

## `RMLBuilder` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_mapping_builder.py#L4)

```python
class RMLBuilder(ontology_uri, resource_uri, maps=[])
```

Utility class for combining one or more `TriplesMap` objects into a complete RML mapping document with the standard prefixes used by the library.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `ontology_uri` | `str` | required | URI used to define the `onto:` prefix in the generated mapping. |
| `resource_uri` | `str` | required | URI used to define the `resource:` prefix in the generated mapping. |
| `maps` | `list[TriplesMap]` | `[]` | Triples maps to include in the exported mapping document. |

### Methods

#### `RMLBuilder.load_prefixes()` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_mapping_builder.py#L11)

```python
load_prefixes()
```

Return the default RML/R2RML, XSD, GeoSPARQL, ontology, and resource prefixes used by the generated mapping.

**Returns:** `list[str]` containing prefix declarations.

#### `RMLBuilder.export_as_string()` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_mapping_builder.py#L26)

```python
export_as_string()
```

Export all configured `TriplesMap` objects as a single RML mapping string.

**Returns:** `str` containing the complete mapping document.

---

## `TriplesMap` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L4)

```python
class TriplesMap(ontology_uri, resource_uri, name=None)
```

Programmatic builder for a single RML/R2RML `rr:TriplesMap`. Use this class when you want to manually define the logical source, subject map, predicate-object maps, joins, or template object maps.

### Parameters

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `ontology_uri` | `str` | required | URI prefix used for generated ontology terms. |
| `resource_uri` | `str` | required | URI prefix used in generated subject templates. |
| `name` | `str \| None` | `None` | Optional triples map name. If omitted, it is derived from the input source in `add_logical_source()`. |

### Methods

#### `TriplesMap.add_logical_source(input_data_source, reference_formulation, iterator=None)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L17)

```python
add_logical_source(input_data_source, reference_formulation, iterator=None)
```

Define the RML logical source for this triples map.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `input_data_source` | `str` | required | Path to the input data source referenced by the mapping. |
| `reference_formulation` | `str` | required | RML reference formulation, for example `"ql:CSV"`, `"ql:JSONPath"`, or `"ql:XPath"`. |
| `iterator` | `str \| None` | `None` | Optional iterator, such as a JSONPath or XPath expression. |

#### `TriplesMap.add_subject_map(id_field, subject_class=None, graph=None)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L23)

```python
add_subject_map(id_field, subject_class=None, graph=None)
```

Define the subject map template for generated subjects.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `id_field` | `str` | required | Field/reference used inside the generated subject URI template. |
| `subject_class` | `str \| None` | `None` | Optional class name emitted as `rr:class onto:<subject_class>`. |
| `graph` | `str \| None` | `None` | Optional graph URI used to create an `rr:graphMap`. |

#### `TriplesMap.add_predicate_object_map(predicate_name, reference, datatype=None, prefix=None)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L27)

```python
add_predicate_object_map(predicate_name, reference, datatype=None, prefix=None)
```

Add a predicate-object map that reads literal values from a source reference.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `predicate_name` | `str` | required | Predicate local name. By default it is emitted under the `onto:` prefix. |
| `reference` | `str` | required | Source field/reference used as the object value. |
| `datatype` | `str \| None` | `None` | Optional datatype hint. Recognized values include `"bool"`, `"int"`, `"float"`, `"wkt"`; other values default to string. |
| `prefix` | `str \| None` | `None` | Optional prefix override for the predicate. |

#### `TriplesMap.add_predicate_object_map_on_join(predicate_name, foreign_map, child, parent)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L31)

```python
add_predicate_object_map_on_join(predicate_name, foreign_map, child, parent)
```

Add a predicate-object map that joins this map with another triples map.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `predicate_name` | `str` | required | Predicate local name for the relationship. |
| `foreign_map` | `TriplesMap` | required | Parent/target triples map. |
| `child` | `str` | required | Child join field. |
| `parent` | `str` | required | Parent join field. |

#### `TriplesMap.add_predicate_object_map_on_reference(predicate_name, refObjectMap)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L35)

```python
add_predicate_object_map_on_reference(predicate_name, refObjectMap)
```

Add a predicate-object map that points to a separately declared `rr:RefObjectMap`.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `predicate_name` | `str` | required | Predicate local name for the relationship. |
| `refObjectMap` | `str` | required | Reference object map identifier. |

#### `TriplesMap.add_predicate_object_map_with_template(predicate_name, template, prefix=None)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L39)

```python
add_predicate_object_map_with_template(predicate_name, template, prefix=None)
```

Add a predicate-object map whose object is generated from an RML/R2RML template.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `predicate_name` | `str` | required | Predicate local name. |
| `template` | `str` | required | Object URI template. |
| `prefix` | `str \| None` | `None` | Optional predicate prefix override. |

#### `TriplesMap.add_ref_object_map(name, parentMap, child, parent)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L43)

```python
add_ref_object_map(name, parentMap, child, parent)
```

Register a reusable reference object map.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `name` | `str` | required | RefObjectMap identifier. |
| `parentMap` | `TriplesMap` | required | Parent triples map. |
| `child` | `str` | required | Child join field. |
| `parent` | `str` | required | Parent join field. |


#### `TriplesMap.export_as_string()` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_triples_map.py#L46)

```python
export_as_string()
```

Serialize this triples map as an RML mapping fragment.

**Returns:** `str` containing the mapping fragment.

**Raises:** `Exception` if the logical source or subject map has not been initialized.

### Example

```python
from toposkg.converter.rml.toposkg_lib_triples_map import TriplesMap
from toposkg.converter.rml.toposkg_lib_mapping_builder import RMLBuilder

places = TriplesMap(
    ontology_uri="https://example.org/ontology/",
    resource_uri="https://example.org/resource/",
    name="PlacesMap",
)
places.add_logical_source("data/places.csv", "ql:CSV")
places.add_subject_map("id", subject_class="Place")
places.add_predicate_object_map("name", "name", datatype="string")
places.add_predicate_object_map("population", "population", datatype="int")

builder = RMLBuilder(
    ontology_uri="https://example.org/ontology/",
    resource_uri="https://example.org/resource/",
    maps=[places],
)
mapping = builder.export_as_string()
```

---

## `RMLModule` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_rml_module.py#L5)

```python
class RMLModule()
```

Small wrapper around `morph_kgc` for materializing RDF triples from an RML mapping file.

### Methods

#### `RMLModule.generate_triples(mapping_file)` [source](https://github.com/KwtsPls/ToposKG/tree/main/toposkg_lib/toposkg/converter/rml/toposkg_lib_rml_module.py#L9)

```python
generate_triples(mapping_file)
```

Materialize RDF triples from a mapping file.

| Parameter | Type | Default | Description |
|---|---:|---:|---|
| `mapping_file` | `str` | required | Path to the RML mapping file. |

**Returns:** `rdflib.Graph` containing the materialized triples.

### Example

```python
from toposkg.converter.rml.toposkg_lib_rml_module import RMLModule

module = RMLModule()
graph = module.generate_triples("mappings/places.ttl")
graph.serialize(destination="out/places.nt", format="nt")
```
