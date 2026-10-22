# MultiGlobeQA / ToposKG topology audit

This part is broken in three parts. If you only care for reproducing the final part of the evaluation look at section C and use the files uploaded here and in [Harvard Dataverse](https://dataverse.harvard.edu/previewurl.xhtml?token=bd996232-2bd2-4e37-86e9-6fd4ee5851da).

## Requirements

- Python 3.10+, pyarrow, shapely. 
- Java 8+
- ToposKG data in modular format
- MultiGlobeQA data (can be downloaded from this [link](https://zenodo.org/records/21786184))

## A. Pre-processing

```bash
python3 a_download.py
```

This command downloads data from huggingface and saves them under a directory named data/. This directory contains all relevant info from the hugging face [repo](https://huggingface.co/datasets/aiana94/MultiGlobeQA/tree/main) of MultiGlobeQA.

```bash
python3 b_extract_topology_questions.py \
  --input-dir data/raw/questions/eng/large/ \
  --out results/multiglobeqa_topology_questions.csv
```

This creates a first draft of the topological questions that might have potential consistency issues.

```bash
python3 c_build_topology_entity_files.py \
  --input results/multiglobeqa_topology_questions.csv \
  --out-dir results/multiglobeqa_selected 
```
This creates a first pass of the unique_entities.csv with all possible countries.

For the next part, you need to download and extract the .parquet files for worldkg and osmh3kg from the MultiGlobeQA [repo](https://huggingface.co/datasets/aiana94/MultiGlobeQA/tree/main).

```bash
python3 d_kg_country_match_parquet.py \
  --kg-source worldkg \
  --kg-dir /path/to/worldkg/parquet/ \
  --entities unique_entities.csv \
  --question-entities question_entities.csv \
  --out-dir results/worldkg_country \
  --workers 8 \
  --batch-size 250000 \
  
python3 d_kg_country_match_parquet.py \
  --kg-source osmh3kg \
  --kg-dir /path/to/osmh3kg/parquet/ \
  --entities unique_entities.csv \
  --question-entities question_entities.csv \
  --out-dir results/osmh3kg_country \
  --workers 8 \
  --batch-size 250000 \
```

This provides an initial mapping between entities in questions and data from the knowledge graphs they belong to.

```bash
python3 e_assign_entity_countries_local.py \
  --matches results/osmh3kg_country/osmh3kg_country_matches.csv results/worldkg_country/worldkg_country_matches.csv \
  --countries countries.geojson \
  --out-dir results/entity_countries
```

This finally creates a directory with a full mapping between countries and entities. This .csv file has the following columns: `source_kg,entity_id,name,country` and is named entity_countries.csv. This can be brought to the same directory with the scripts and renamed to multiglobeqa_entities.csv for compliance with the rest of the commands.


## B. Materialization

```bash
python3 01_materialize_countries.py \
  --entities multiglobeqa_entities.csv \
  --country-codes countries.csv \
  --countries-dir /data/topos/countries \
  --materializer /path/to/materialize_topology.sh \
  --out-dir results/countries
```

This creates `results/countries/countries.nt`, `country_mappings.nt`, `country_status.csv`, and `by_country/<code>/mappings.nt`. Existing successful per-country outputs are reused on restart. Countries absent from the code CSV or directory appear in `country_status.csv` (not silently invented). The country NT is the concatenation of the available country files, *not* an ontology-reasoned union.

```bash
python3 02_extract_entity_geometries.py \
  --kg-source osmh3kg \
  --parquet-dir /data/osmh3kg \
  --entities multiglobeqa_entities.csv \
  --out-dir results/osmh3kg \
  --batch-size 250000

python3 02_extract_entity_geometries.py \
  --kg-source worldkg \
  --parquet-dir /data/worldkg \
  --entities multiglobeqa_entities.csv \
  --out-dir results/worldkg \
  --batch-size 250000
```

This emits `entity_geometries.nt`, `entity_geometries.csv`, `entity_uri_mapping.csv`, and `missing_geometry_ids.txt` separately for each KG. It recognizes RDF-triple Parquet columns named `subject,predicate,object` (case-insensitive), but *not arbitrary flattened property tables*. It searches both entity subject triples and their linked geometry nodes. Original entity subject URIs are recorded. WKT is emitted as GeoSPARQL `geo:wktLiteral` in its original coordinates; supply only source data whose CRS is supported by your JEDAI workflow.

```bash
python3 03_materialize_entity_countries.py \
  --countries-nt results/countries/countries.nt \
  --country-mappings results/countries/country_mappings.nt \
  --entity-geometry-nt results/osmh3kg/entity_geometries.nt \
  --entity-geometry-nt results/worldkg/entity_geometries.nt \
  --materializer /path/to/materialize_topology.sh \
  --out-dir results/joint
```

Outputs: `results/joint/entities_and_countries.nt`, `entity_country_mappings.nt`, `mappings.nt` (deduplicated union of the two materialization output files).

## C. Question evaluation

```bash
python3 04_evaluate_questions.py \
  --questions multiglobeqa_topology_questions.csv \
  --entity-geometries results/osmh3kg/entity_geometries.csv \
  --entity-geometries results/worldkg/entity_geometries.csv \
  --mappings results/joint/mappings.nt \
  --out-dir results/evaluation
```

Outputs: `question_evaluation.csv`, `verified_inconsistencies.csv`, `evaluation_summary.csv`.

Statuses:
- `consistent`: complete, valid geometries or logically sufficient materialized relation support the gold boolean.
- `inconsistent`: complete, valid geometries or logically sufficient materialized relation refute the gold boolean.
- `unverifiable`: unsupported aggregate/selection template; missing, invalid, or multiple geometries; or insufficient mapping evidence.

Supported direct two-entity Boolean templates: `13.1` and `14.1` (intersects), `19.1` (overlaps), `20.1` and `21.1` (touches), `22.1` (disjoint), `23.1` (contains), `31.1` (within). `28.1` administrative membership is not equivalent to spatial inclusion and is conservatively left unverifiable. `15-18`, `29-30` and `32.x` aggregate/argmax/selection templates require the original candidate population or complete source KG logic and are left unverifiable. Full national boundary datasets are not needed to recompute entity-entity boolean relationships, *but both entities' exact source geometries are required*.
