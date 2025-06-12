#!/bin/bash

# Check for required arguments
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <continent.csv>"
  exit 1
fi

declare -i i=0
input_file="$1"
while IFS= read -r line
do
  if [ "$i" -ne "0" ]; then
    IFS=',' read -r -a array <<< "$line"
    echo "Working on ${array[0]}..."
    ./gaul_workflow.sh "${array[0]}"
  fi
i=$((i+1))
done < "$input_file"
