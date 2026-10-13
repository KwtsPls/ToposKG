# MultiGlobeQA / ToposKG topology audit

This project prepares ToposKG spatial mappings and audits exactly these question families:

- `osmh3kg` / `C`
- `osmh3kg` / `E`
- `worldkg` / `C`

**Do not equate disagreement with the source KG geometry with independent geographic truth.** This measures discrepancies between benchmark gold answers and the recomputed geometry representation. The evaluator does not call absent mapping triples `false`.

## Requirements

Python 3.10+, `pip install pyarrow shapely`. Your existing `materialize_topology.sh`, `jedai_spatial_pipeline.sh`, `jedai_map.sh`, and the interlinking JAR must be in the same directory, as in your setup. The provided country file must have CSV columns `country,uri,code`. Country datasets must be `<countries-root>/<Country>/<Country>.nt`. The benchmark entity CSV must have columns `source_kg,entity_id,name,country`.
The MultiGlobeQA data can be downloaded from this [link](https://zenodo.org/records/21786184)

## A. Materialization

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

The extractor uses **full** WKT (not 200-character previews). It emits `entity_geometries.nt`, `entity_geometries.csv`, `entity_uri_mapping.csv`, and `missing_geometry_ids.txt` separately for each KG. It recognizes RDF-triple Parquet columns named `subject,predicate,object` (case-insensitive), but *not arbitrary flattened property tables*. It searches both entity subject triples and their linked geometry nodes. Original entity subject URIs are recorded. WKT is emitted as GeoSPARQL `geo:wktLiteral` in its original coordinates; supply only source data whose CRS is supported by your JEDAI workflow.

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

**Caution:** Your supplied materializer interlinks every `_no` source in the combined file against all geometries, potentially producing *more than entity-to-country mappings* (including self matches, entity-to-entity, country-to-country). If that is undesirable, modify the materializer to use an explicit source/target N-Triples input rather than `grep _no`. For the benchmark audit the evaluator does not treat these extra relations as verified country containment.

## B. Question evaluation

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

Spatial predicate implications are conservative and may require customization for your interlinker's actual vocabulary. Verify especially whether `touches` is intended as GeoSPARQL `sfTouches` rather than an arbitrary proximity-based 'adjacency'.

## NAACL table

| KG | Spatial family | Total Q | Consistent (n) | Inconsistent (n) | Unverifiable (n) | Inconsistency among verifiable (%) |
|---|---|---:|---:|---:|---:|---:|
| OSMH3KG | C | ... | ... | ... | ... | ... |
| OSMH3KG | E | ... | ... | ... | ... | ... |
| WorldKG | C | ... | ... | ... | ... | ... |

Denominator for the last column must be `consistent + inconsistent`, and report coverage `(consistent + inconsistent) / all questions` separately. Do not count `unverifiable` as consistent or inconsistent.
