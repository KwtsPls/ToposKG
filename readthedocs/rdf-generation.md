# RDF generation

This page describes how ToposKG converts input data into RDF triples.

## Overview

The RDF generation process takes normalized geospatial entities and serializes them as RDF resources. Each generated entity may include:

- a URI
- one or more RDF types
- labels or names
- source attributes
- geometry information
- links to related entities

## Basic RDF structure

A generated entity may look like this in Turtle:

```turtle
@prefix topos: <https://example.org/toposkg/ontology/> .
@prefix geo: <http://www.opengis.net/ont/geosparql#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<https://example.org/toposkg/resource/waterbody/12345>
    a topos:Waterbody ;
    rdfs:label "Example Lake"@en ;
    geo:hasGeometry <https://example.org/toposkg/resource/geometry/12345> .

<https://example.org/toposkg/resource/geometry/12345>
    a geo:Geometry ;
    geo:asWKT "POINT(23.72 37.98)"^^geo:wktLiteral .
```

## Entity triples

For each input entity, ToposKG should generate core triples such as:

```text
entity-uri rdf:type class-uri
entity-uri rdfs:label label-literal
entity-uri geo:hasGeometry geometry-uri
```

Additional triples may be generated depending on the available input attributes.

## Geometry triples

Geometry triples represent spatial information using GeoSPARQL-compatible properties.

Typical structure:

```text
entity-uri geo:hasGeometry geometry-uri
geometry-uri geo:asWKT wkt-literal
```

Supported geometry types may include:

- `Point`
- `LineString`
- `Polygon`
- `MultiPolygon`

## Attribute mapping

Input attributes can be mapped to RDF predicates.

Example input attribute:

```text
population=10000
```

Example RDF output:

```turtle
<https://example.org/toposkg/resource/admin/1>
    topos:population "10000"^^<http://www.w3.org/2001/XMLSchema#integer> .
```

## Output formats

ToposKG may support multiple RDF serialization formats.

| Format | Extension | Description |
| --- | --- | --- |
| N-Triples | `.nt` | Simple line-based RDF serialization. Useful for large files. |
| Turtle | `.ttl` | Under construction |
| RDF/XML | `.rdf` | Under construction |

## Related API pages

- [Naive mapping API](naive_mappings_api.md): direct converters for CSV, JSON, XML, GeoJSON, GML, KML, and Shapefiles.
- [RML mapping API](rml_mappings_api.md): RML builders, mapping generators, triples maps, and RDF generation modules.
