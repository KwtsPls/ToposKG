import os
import sys
import argparse
import pandas as pd
import networkx
from networkx import draw, Graph

from pyjedai.evaluation import Evaluation
from pyjedai.datamodel import Data
from pyjedai.vector_based_blocking import EmbeddingsNNBlockBuilding

# --- Argument parsing ---
parser = argparse.ArgumentParser(description="Entity matching with PyJedAI.")
parser.add_argument('--d1', required=True, help='Path to the first CSV file')
parser.add_argument('--d2', required=True, help='Path to the second CSV file')
parser.add_argument('--output', required=True, help='Path to the output CSV file')

args = parser.parse_args()

# --- Load data ---
d1 = pd.read_csv(args.d1, sep=',', engine='python', na_filter=False).astype(str)
d2 = pd.read_csv(args.d2, sep=',', engine='python', na_filter=False).astype(str)

d1 = d1[["entity", "hasName"]]
d2 = d2[["entity", "hasName", "hasNameEn"]]

print(d1.head())
print(d2.head())

# --- Set up data ---
attr1 = d1.columns[1:].to_list()
attr2 = d2.columns[1:].to_list()

data = Data(dataset_1=d1,
            attributes_1=attr1,
            id_column_name_1='entity',
            dataset_2=d2,
            attributes_2=attr2,
            id_column_name_2='entity')

emb = EmbeddingsNNBlockBuilding(vectorizer='sminilm',
                                similarity_search='faiss')

blocks, g = emb.build_blocks(data,
                             top_k=1,
                             similarity_distance='cosine',
                             load_embeddings_if_exist=False,
                             save_embeddings=False,
                             with_entity_matching=True)

mapping_df = emb.export_to_df(blocks)

# --- Merge results ---
merged1 = pd.merge(d1, mapping_df, left_on='entity', right_on='id1', how='left')
final_df = pd.merge(merged1, d2, left_on='id2', right_on='entity', how='left', suffixes=('_gaul', '_osm'))
final_df = final_df.drop(columns=['id1', 'id2'])

# --- Save output ---
final_df.to_csv(args.output, index=False)
