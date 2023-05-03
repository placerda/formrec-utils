"""
Title: Form Recognizer Library
Author: Paulo Lacerda
Description: Library to analyze documents using Form Recognizer REST API and SDK.

"""
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient
import os
import requests
import json
import time
import base64

endpoint =  os.getenv("FORM_RECOGNIZER_ENDPOINT")
api_key =  os.getenv("FORM_RECOGNIZER_KEY")

''' this function creates a base64EncodedContent from a file path '''
def get_base64_encoded_content(filepath):
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_document_rest(filepath, model, features=[]):
    base64EncodedContent = get_base64_encoded_content(filepath)

    # Request headers
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": api_key
    }

    # Request body
    body = {
        "base64Source": base64EncodedContent
    }

    # if user wants to get features
    if len(features) > 0:
        features_str = ",".join(features) # TODO: review if this is the correct way to add a list of features   
        request_endpoint = f"{endpoint}formrecognizer/documentModels/{model}:analyze?features={features_str}&api-version=2023-02-28-preview"
    else:
        request_endpoint = f"{endpoint}formrecognizer/documentModels/{model}:analyze?api-version=2023-02-28-preview"
    
    # Send request
    response = requests.post(request_endpoint, headers=headers, json=body)

    # Parse response
    if response.status_code == 202:
        # Request accepted, get operation ID
        operation_id = response.headers["Operation-Location"].split("/")[-1]
        # print("Operation ID:", operation_id)
    else:
        # Request failed
        print("Error request: ", response.text)
        exit()

    # Poll for result
    result_endpoint = f"{endpoint}formrecognizer/documentModels/prebuilt-layout/analyzeResults/{operation_id}"
    result_headers = headers.copy()
    result_headers["Content-Type"] = "application/json-patch+json"
    result = {}

    while True:
        result_response = requests.get(result_endpoint, headers=result_headers)
        result_json = json.loads(result_response.text)

        if result_response.status_code != 200 or result_json["status"] == "failed":
            # Request failed
            print("Error result: ", result_response.text)
            break

        if result_json["status"] == "succeeded":
            # Request succeeded, print result
            # print("Result:", json.dumps(json.dumps(result_json['analyzeResult']), indent=4))
            result = result_json['analyzeResult']
            break

        # Request still processing, wait and try again
        time.sleep(1)

    return result

def analyze_document_sdk(filepath, model):
    # connect to service
    document_analysis_client = DocumentAnalysisClient(
        endpoint=endpoint, credential=AzureKeyCredential(api_key)
    )

    # analyze document file
    with open(filepath, "rb") as f:
        poller = document_analysis_client.begin_analyze_document(
            model, document=f
        )
    result = poller.result()
    return result
