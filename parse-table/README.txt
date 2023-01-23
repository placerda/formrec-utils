# How to Execute

1. update .env file in source folder with your own credentials

FORM_RECOGNIZER_ENDPOINT=https://[FORM_RESOURCE_NAME].cognitiveservices.azure.com/
FORM_RECOGNIZER_KEY=[YOUR_KEY]

2. update environment

pip install -r requirements.txt

3. add pdf file to data folder (ex: ./data/Sample 1.pdf) 

4. execute the script

python ./source/parse_table.py
