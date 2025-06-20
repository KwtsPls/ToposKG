import csv
import re
from typing import List
import pandas as pd

from collections import OrderedDict
from rdflib import Graph, Literal, URIRef

from pyjedai.datamodel import Data
from pyjedai.vector_based_blocking import EmbeddingsNNBlockBuilding

GEOSPARQL_PREFIX = "http://www.opengis.net/ont/geosparql#"

def clean_predicate(uri):
    uri = uri.strip("<>")
    return uri.split("/")[-1] if "/" in uri else uri.split("#")[-1]

def escape_csv(value):
    if value is None:
        return ""
    if ',' in value or '"' in value:
        return '"' + value.replace('"', '""') + '"'
    return value

def toposkg_nt_to_csv(input_file: str, predicates: List[str], output_file: str):
    g = Graph()
    g.parse(input_file, format='nt')

    data = OrderedDict()

    # Collect data
    for predicate in predicates:
        # print(predicate)
        for s, o in g.subject_objects(URIRef(predicate)):
            # print(f"Processing: {s} - {predicate} - {o}")
            s_str = str(s)
            p_str = predicate
            o_str = str(o)

            if p_str.startswith(GEOSPARQL_PREFIX):
                continue

            if not isinstance(o, Literal):
                continue

            if s_str not in data:
                data[s_str] = OrderedDict()
            if clean_predicate(p_str) not in data[s_str]:
                data[s_str][clean_predicate(p_str)] = o_str

    # Write CSV
    with open(output_file, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header
        header = ['entity'] + [clean_predicate(p) for p in predicates]
        writer.writerow(header)

        # Rows
        for entity, predicates in data.items():
            row = [escape_csv(entity)] + [escape_csv(predicates.get(p, "")) for p in predicates]
            writer.writerow(row)

    return pd.read_csv(output_file, sep=',', engine='python', na_filter=False).astype(str)

def toposkg_link_csvs(d1_path, id_column_name_1, d2_path, id_column_name_2, output_path):
    # Load data
    d1 = pd.read_csv(d1_path, sep=',', engine='python', na_filter=False).astype(str)
    d2 = pd.read_csv(d2_path, sep=',', engine='python', na_filter=False).astype(str)

    return toposkg_link_dataframes(d1, id_column_name_1, d2, id_column_name_2, output_path)

def toposkg_link_dataframes(d1, id_column_name_1, d2, id_column_name_2, output_path):
    # Set up data
    attr1 = d1.columns[:].to_list()
    attr2 = d2.columns[:].to_list()

    data = Data(dataset_1=d1,
                attributes_1=attr1,
                id_column_name_1=id_column_name_1,
                dataset_2=d2,
                attributes_2=attr2,
                id_column_name_2=id_column_name_2)

    emb = EmbeddingsNNBlockBuilding(vectorizer='sminilm',
                                    similarity_search='faiss')

    blocks, g = emb.build_blocks(data,
                                 top_k=1,
                                 similarity_distance='cosine',
                                 load_embeddings_if_exist=False,
                                 save_embeddings=False,
                                 with_entity_matching=True)

    mapping_df = emb.export_to_df(blocks)
    
    print(mapping_df)

    # Merge results
    merged1 = pd.merge(d1, mapping_df, left_on=id_column_name_1, right_on='id1', how='left')
    final_df = pd.merge(merged1, d2, left_on='id2', right_on=id_column_name_2, how='left', suffixes=('_1', '_2'))
    final_df = final_df.drop(columns=['id1', 'id2'])

    # Save output
    final_df.to_csv(output_path, index=False)

    return final_df

def toposkg_csv_to_nt(input_file: str, column_id_name: str, output_file: str):
    df = pd.read_csv(input_file, sep=',', engine='python', na_filter=False).astype(str)

    g = Graph()

    for _, row in df.iterrows():
        entity = row[column_id_name]
        for predicate, value in row.items():
            if predicate == column_id_name:
                continue
            if value:
                g.add((URIRef(entity), URIRef("http://toposkg.di.uoa.gr/ontology/" + predicate), Literal(value)))

    g.serialize(destination=output_file, format='nt')
    return g


if __name__ == "__main__":
    # toposkg_nt_to_csv("/home/sergios/ToposKG/us_states_gaul.nt", ['http://toposkg.di.uoa.gr/ontology/hasName'], "/home/sergios/ToposKG/us_states_gaul_linking.csv")
    
    gaul_df = pd.read_csv("/home/sergios/ToposKG/us_states_gaul_linking.csv", sep=',', engine='python', na_filter=False).astype(str)
    target_df = pd.read_csv("/home/sergios/ToposKG/us_states_test_data.csv", sep=',', engine='python', na_filter=False).astype(str)
    
    # target_df.drop(columns=['test_data_1'], inplace=True, errors='ignore')
    # target_df.drop(columns=['test_data_2'], inplace=True, errors='ignore')
    
    toposkg_link_dataframes(
        d1=gaul_df,
        id_column_name_1="hasName",
        d2=target_df,
        id_column_name_2="State",
        output_path="/home/sergios/ToposKG/link_output_dfs.csv"
    )
    
    toposkg_csv_to_nt(
        input_file="/home/sergios/ToposKG/link_output_dfs.csv",
        column_id_name="entity",
        output_file="/home/sergios/ToposKG/link_output_dfs.nt"
    )
    
    # toposkg_link_csvs(
    #     d1_path="/home/sergios/ToposKG/us_states_gaul_linking.csv",
    #     id_column_name_1="entity",
    #     d2_path="/home/sergios/ToposKG/us_states_test_data.csv",
    #     id_column_name_2="State",
    #     output_path="/home/sergios/ToposKG/link_output.csv"
    # )