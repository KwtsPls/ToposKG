# ToposKG statistics

This directory holds useful statistical information about ToposKG data. The collection of this information is done mainly 1) per country and 2) globally


## Total number of geospatial data per type:

| geometry_type | count |
|---|---:|
| LineString | 45176391 |
| MultiPolygon | 47823518 |
| Point | 17015254 | 
| Polygon | 40947 |
| Total | 110050380 |


## Factually Incorrect GAUL adminstrative untis

This two .csv files provide ifnromation about either deprecated, older, or incorrect administrative data information. Bellow is listed the global count of incorrect adminsatrative data:

| level | total_faulty_entities | faulty_country_count |
|---:|---:|---:|
| 0 | 16 | 11 |
| 1 | 214 | 30 |
| 2 | 1074 | 46 |

Information per country can be seen in `factually_incorrect_gaul_per_country.csv`

## Gap analysis

The infromation presented here refers to administrative units that create gaps on their upper level. The validation process is better described in the ToposKG paper. Bellow are presented the global gaps per adminstrative level.

| level_pair | parent_level | child_level | country_count | parent_count | child_count | parents_with_children | parents_without_children | parents_with_gaps | gap_piece_count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0-1 | 0 | 1 | 142 | 137 | 2356 | 124 | 13 | 13 | 132 |
| 1-2 | 1 | 2 | 142 | 2356 | 42104 | 2031 | 325 | 325 | 532 |

Information per country can be seen in `gaps_per_country.csv`

## OSM Discovered Upper Administrative Levels

These values refer to original OSM data, that did not have any information on upper level adminsitrative units, mainly through wikidata. The discovery process is better described in the ToposKG paper. Here are presented the global data:

| level | total_unique_no_uri_count | country_count |
|---:|---:|---:|
| 1 | 9968 | 166 |
| 2 | 28803 | 148 |
| 3 | 111123 | 118 |
| 4 | 205849 | 86 |
| 5 | 156887 | 53 |
| 6 | 180242 | 30 |
| 7 | 52263 | 11 |
| 8 | 21782 | 3 |

Information per country can be seen in `discovered_osm_upper_units_per_country.csv`

## Invalid Geometry Count

A simple error analysis on invalid geometries. The validity was checked through JTS tools through the isValid() method. Geometries were then currected through .buffer(0). Here are presented the global data:

| geometry_type | invalid_geometry_count | parsed_geometry_count | parse_error_count |
|---|---:|---:|---:|
| LineString | 0 | 45176391 | 0 |
| MultiPolygon | 118 | 47823518 | 0 |
| Point | 0 | 17015254 | 0 |
| Polygon | 196 | 40947 | 0 |
| UNKNOWN | 0 | 0 | 4 |
| ALL_TYPES | 314 | 110050380 | 4 |

| Source | geometry_type | invalid_geometry_count | parsed_geometry_count | parse_error_count |
|---|---|---:|---:|---:|
| GMBA | MultiPolygon | 5 | 2699 | 0 |
| GMBA | Polygon | 0 | 2930 | 0 |
| GMBA | ALL_TYPES | 5 | 5629 | 0 |
| MarineRegions | MultiPolygon | 0 | 4 | 0 |
| MarineRegions | Polygon | 0 | 97 | 0 |
| MarineRegions | ALL_TYPES | 0 | 101 | 0 |

Information per country can be seen in `invalid_geometries_per_country.csv`

## Coverage Analysis

Some further statistical information about classes, under the `coverage_results` subdir.

### GAUL entities per level

| source | level | country_count | total_entity_count |
|---|---:|---:|---:|
| GAUL | 0 | 172 | 173 |
| GAUL | 1 | 165 | 2677 |
| GAUL | 2 | 141 | 42104 |

### Entities per class

Entities per class data can be found here: `coverage_results/entities_by_class_and_source.csv`

### Natural entities per class

| feature_class | source | entity_count | country_or_global_file_count | countries_or_global_files_with_data |
|---|---|---:|---:|---:|
| forests | OSM | 21239112 | 181 | 174 |
| mountains | GMBA | 5629 | 1 | 1 |
| pois | OSM | 45036291 | 181 | 174 |
| seas | MarineRegions | 101 | 1 | 1 |
| waterbodies | OSM | 43029412 | 181 | 174 |

## GAUL complete level 0-2 coverage

Countries with complete GAUL coverage (levels 0 to 2), can be found in `coverage_results/gaul_complete_level_0_2_coverage.csv`