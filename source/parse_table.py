import parse_table_utils as parse_table_utils
import json
import os
import pandas as pd
from dotenv import load_dotenv, find_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

INPUT_FILE  = "data/Sample 6.pdf"

# connect to service
load_dotenv(find_dotenv())
key =  os.getenv("FORM_RECOGNIZER_KEY")
endpoint =  os.getenv("FORM_RECOGNIZER_ENDPOINT")
document_analysis_client = DocumentAnalysisClient(
    endpoint=endpoint, credential=AzureKeyCredential(key)
)

# analyze document file
with open(INPUT_FILE, "rb") as f:
    poller = document_analysis_client.begin_analyze_document(
        "prebuilt-layout", document=f
    )
result = poller.result()

# parse document's tables in a tree structure (each table is a tree)
trees = parse_table_utils.parse_json_result(result)

# show results in console
for tree in trees:
    tree_formatted = json.dumps(tree, indent=4)
    print(tree_formatted, "\n\n")

# format trees in dataframe format for export as csv
count = 1
for tree in trees:
    df = parse_table_utils.get_dataframe(tree)
    out_filename = f"{INPUT_FILE[:-4]} {str(count).zfill(3)}.csv" # example Sample 4 001.csv
    df.to_csv(out_filename, index=False, header=True)
    count += 1

print("DONE")