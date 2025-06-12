# Topos-Parser

## Compilation

Prerequisites: Java 17 and Maven 3.6.3

To compile run the following command

    mvn clean package shade:shade

## Execution

To execute the various parsing capabilities of Topos-Parser run one of the following commands:

    java -jar target/Topos-parser-1.0-SNAPSHOT.jar [command] [args...]

The available commands are listed below:

  - create
  - osm
  - water
  - poi
  - forest
  - fix
  - fix_level
  - validate_level
  - validate_neighbor
  - osm_hierarchy
  - osm_collect_missingosm_collect_missing
  - rank_intersections
  - prepare_for_linking
  - connection

We also provide a number of bash scripts that automate the process of the above command.
