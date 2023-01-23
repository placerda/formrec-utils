# How to Execute

1. update .env file in source folder with your own credentials

FORM_RECOGNIZER_ENDPOINT=https://[FORM_RESOURCE_NAME].cognitiveservices.azure.com/
FORM_RECOGNIZER_KEY=[YOUR_KEY]

2. update environment

pip install -r requirements.txt

3. Parse table utility: 

Extract tables with hierarchical items.

Example:

| Items        | Value |
| Item 1       |   1.0 |
|     Item 1.1 |   1.0 |
|     Item 1.2 |   1.0 |

3.1. add pdf file to data folder (ex: ./data/Sample 1.pdf) 

3.2. review script parameters

```
parse_table:

INPUT_FILE  = "data/Sample 1.pdf" (input file name)

parse_table_utils.py:

THRESHOLD = 0.05 (minimum indent width)
IGNORE_LIST = ["Subtotal"] # Ignore these items when creating the tree structure
```

3.3. execute the script

python ./source/parse_table.py