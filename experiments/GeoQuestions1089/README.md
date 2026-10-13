# GeoQuestions1089 Benchmark

## Requirements

- Python 3.10
- YAGO2geo data from the anonymized repo
- Java 1.8

# Setup

Load the .nt data into the Docker file. The dockerfile is inside the general-graphdb-docker directory and contains information and commands for the loading

## Command execution

    python3 evaluate_geoquestions1089.py 
        --questions GeoQuestions1089_topos.json 
        --answers GeoQuestions1089_answers.json 
        --endpoint "docker_endpoint" 
        --gost GoST-1.0-SNAPSHOT.jar  
        --out-dir evaluation_results