#!/bin/bash

input="$1"
while IFS= read -r line
do
  IFS=',' read -a array <<< "$line"
  echo "${array[0],,} " "${array[1],,}"
  ./osm_workflow.sh "${array[0]}" "${array[1],,}"
done < "$input"
