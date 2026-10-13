# SpaRAGraph Benchmark


## Inputs
- `sparagraph_topological_questions.csv`: columns `source_file,source_type,source_row,query,truth,...`
- `CSZt.nt`: SpaRAGraph N-Triples
- `toposkg_spatial_relations.nt`: GeoSPARQL relations for ToposKG entities
- `toposkg_entity_metadata.nt`: Census / GAUL metadata (combine both if necessary)

## Run
```bash
python3 validate_sparagraph.py \
  --questions sparagraph_topological_questions.csv \
  --kg CSZt.nt \
  --mappings toposkg_spatial_relations.nt \
  --entities toposkg_entity_metadata.nt \
  --out audit_v3
```

## Gold-answer semantics

For **yes/no** `A adjacent to and north of B`:
- `yes` entails `sfTouches(A,B)`; explicit non-touching reference evidence makes the **gold answer inconsistent**.
- `no` does **not** entail non-touching (the direction alone may be wrong); if explicit evidence shows not-touching then `no` is **supported**. If touching is true, the directional answer is **unverifiable** on topology alone.
- For `yes` and reference touching, topology is supported but north/south/etc. is **unchecked**, so the full gold answer is not verified.

For **checkbox** adjacency-plus-direction options: each checked option entails touching, while each unchecked option does not mean non-touching. Only a selected option with proven non-touching can falsify gold using topology alone. Unchecked options can be supported when non-touching is proven, but their direction remains unchecked otherwise.

For **radio** questions: only the selected topological option is treated as a positive gold claim; an unselected radio option is **not** an independently annotated false assertion. Even if the selected option's topological component is supported, exclusive correctness remains unverified (`topology_compatible_radio`), unless a contradiction can refute the selected claim. Selected direction-only or 'none of above' remains unverifiable by topology alone.

For **non-directional** yes/no and checkbox questions, the selected/unselected answer can be compared to explicitly supported or refuted spatial predicates. Missing assertions default to UNKNOWN (open-world), not false.

## Outputs
- `question_results.csv`: original columns, per-question status and evidence counts
- `atomic_checks.csv`: each (entity pair, option, relation), original choice, ToposKG evidence and status
- `summary.json`: counts by question/atom status
- `audit_index.sqlite`: on-disk intermediate indexes

Status meanings:
- `gold_inconsistent`: at least one original gold assertion is conclusively contradicted by non-directional topology (subject to the reference/source alignment being valid)
- `gold_consistent`: evaluated non-directional choices, or provably false directional conjunctions, are supported
- `topology_supported_direction_unchecked`: positive directional choices touch; direction has not been checked
- `topology_compatible_radio`: selected non-directional radio option is supported, but option exclusivity is not verified
- `unverifiable`: mapping missing/ambiguous, reference topology unknown, or topology cannot resolve directional / radio answer
- `skipped`: unsupported question parse or malformed gold

**Caveats:** ToposKG and TIGER 2015 may differ in boundary definitions; geographic reference disagreements require review before labeling as factual errors. `--closed-world` turns absent ToposKG relations into false: use ONLY if the reference relation materialization is complete. The report includes all 1,805 question rows but some can remain unverifiable.
