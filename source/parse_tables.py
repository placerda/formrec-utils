"""
Title: Parse Table
Author: Paulo Lacerda
Description: Program to parse tables from PDFs

"""
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
import logging
import os
import table_parsing_utils
import formrec as fr
from utils import logger

## INPUT FILES ##
files = ["data/Sample 123.pdf"]

class Parser:
    def __init__(self) -> None:
        logger.debug('Creating an instance of Parser')
        self.api_key =  os.getenv("FORM_RECOGNIZER_KEY")
        self.endpoint =  os.getenv("FORM_RECOGNIZER_ENDPOINT")
     
    def parse_tables(self, file):
        logger.info(f"PROCESSING {file}")
        logger.info(f"Analyzing {file} with FormRec")
        result = fr.analyze_document_rest(file, 'prebuilt-layout', features=['ocr.font'])

        # parse document's tables in a tree structure (each table is a tree)
        logger.info(f"Parsing {file} tables")
        trees = table_parsing_utils.parse_json_result(result)

        # format trees in dataframe format to export as csv
        count = 1
        for tree in trees:
            logger.info(f"Formatting {file} table {str(count).zfill(3)} to csv")
            df = table_parsing_utils.get_dataframe(tree)
            out_filename = f"{file[:-4]} {str(count).zfill(3)}.csv" # example Sample 4 001.csv
            df.to_csv(out_filename, index=False, header=True)
            count += 1

def main():
    for file in files:
        parser = Parser()
        parser.parse_tables(file)
    print("DONE")

if __name__ == "__main__":
    main()