## Setup

1. Update .env file in source folder with your own credentials (use .env.template as a reference)

```
FORM_RECOGNIZER_ENDPOINT=https://[FORM_RESOURCE_NAME].cognitiveservices.azure.com/

FORM_RECOGNIZER_KEY=[YOUR_KEY]

AZURE_OPENAI_SERVICE=[AZURE OPENAI SERVICE NAME]

AZURE_OPENAI_GPT_DEPLOYMENT=[AZURE OPENAI DAVINCI 3.0 MODEL DEPLOYMENT NAME]

AZURE_OPENAI_KEY=[AZURE OPENAI SERVICE KEY]

```

2. Update environment

```
pip install -r requirements.txt
```

## Parse table

Parse table script (parse_table.py) extract tables with hierarchical items.
 
Example:
```
| Items        | Value |
| ------------ | ----- |
| Item 1       |   1.0 |
|     Item 1.1 |   1.0 |
|     Item 1.2 |   1.0 |
```

1. Add pdf file to data folder (ex: data/Sample 1.pdf) 

2. Review script parameters

parse_table.py:
```
INPUT_FILE  = "data/Sample 1.pdf" # input file name
```

parse_table_utils.py:
```
THRESHOLD = 0.05 # minimum indent width
IGNORE_LIST = ["Subtotal"] # rows to ignore
```

3. Execute the script

```
python ./source/parse_table.py
```