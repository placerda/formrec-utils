"""
Title: Parse Table Utils
Author: Paulo Lacerda
Description: Utility functions to parse tables from PDFs

"""
import os
import re
import pandas as pd
import azure_openai_utils
from utils import logger

## Global variables ##

PARENT_INDENT_THRESHOLD = 0.05 # Fine tune the indent size accordingly the documents used.
IGNORE_ITEMS_LIST = [] # Ignore items containing these keywords when creating the tree structure. Example IGNORE_ITEMS_LIST = ["Subtotal", "Total"]
MUST_HAVE_COLUMNS = [] # Must have these columns filled to be included in the dataframe. Example: MUST_HAVE_COLUMNS = ["Impl"]
RESERVED_ATTRIBUTES = ['content', 'rowIndex', 'span_offset', 'span_length', 'children', 'styles']

VALIDATE_ATTRIBUTE_PROMPT = open("prompts/validate_attribute_prompt.txt", "r").read()
INFER_COLUMN_NAME_PROMPT = open("prompts/infer_column_name.txt", "r").read()



## General functions ##

''' return empty string if the item is not found in a collection '''
def get_item_value(item, column):
    try:
        return item[column]
    except KeyError:
        return ''

### Functions to create items in tree structure (sub-group hierarchy) ###

''' get the x coordinate of a cell '''
def get_x(pages, content, span_offset, span_length):
    x = 0
    for page in pages:
        lines = page['lines']
        for line in lines:
            if line['content'] in content and line['spans'][0]['offset'] == span_offset: # and line.spans[0].length == span_length:
                x = line['polygon'][0]
                break
    return x

''' get the immediate parent of a cell '''
def get_parent(pages, table, content, rowIndex, span_offset, span_length):
    child_x = get_x(pages, content, span_offset, span_length)
    parent = {'content': "Has no parent", 'rowIndex': -1, 'span_offset': 0, 'span_length': 0}
    for cell in table['cells']:
        # check each cell as a candidate parent, check it to confirm.
        kind = cell['kind'] if 'kind' in cell else 'content' # (default)
        candidate = {
            'content': cell['content'],
            'rowIndex': cell['rowIndex'],
            'columnIndex': cell['columnIndex'],
            'kind': kind
        }
        if candidate['columnIndex'] == 0 and candidate['kind'] == 'content' and len(cell['spans']) > 0:
            candidate['span_offset'] = cell['spans'][0]['offset']
            candidate['span_length'] = cell['spans'][0]['length']          
            candidate_x = get_x(pages, candidate['content'], candidate['span_offset'] , candidate['span_length'])
            if child_x - candidate_x > PARENT_INDENT_THRESHOLD:
                if rowIndex > candidate['rowIndex']:
                    if parent['rowIndex'] < candidate['rowIndex']:
                        parent = candidate
    return parent

''' add a node to the tree structure'''
def add_child(items, parent, node):
    for item in items:
        if parent['span_offset'] == item['span_offset'] and \
            parent['span_length'] == item['span_length'] and \
            parent['content'] == item['content'] and \
            parent['rowIndex'] == item['rowIndex']:
            item['children'].append(node)
            break
        else:
            add_child(item['children'], parent, node)

''' remove line breaks from a string '''
def remove_line_breaks(content):
    return re.sub('\n', ' ', content).strip()

''' add missing headers when they are not present in the table '''
def add_missing_headers(cells, headers, rowIndex, columnIndex):
    _headers = headers
    for cell in cells:
        if cell['rowIndex'] == rowIndex:
            has_header = False
            for header in headers:
                if header['columnIndex'] == cell['columnIndex']:
                    has_header = True
                    break
            if not has_header:
                _headers.append({
                    'content': f"TBD {cell['columnIndex']}",
                    'rowIndex': 0,
                    'columnIndex': cell['columnIndex']
                })
    return _headers

''' populate the node with attribute values '''
def add_values(cells, rowIndex, headers, node):
    # find column indexes
    column_indexes = set([])
    for header in headers:
        column_indexes.add(header['columnIndex'])
    column_indexes = list(column_indexes)
    
    # find header row by looking for the closest header above the current row for each column
    columns = []
    for column_i in column_indexes:
        current_distance = 1000000
        headerRowIndex = 0
        for header in headers:
            rowDistance = rowIndex - header['rowIndex']
            if column_i == header['columnIndex'] and rowDistance < current_distance and rowDistance > 0 and header['content'] != '':
                headerRowIndex = header['rowIndex']
                current_distance = rowDistance

        # define attributes names
        for header in headers:
            if column_i == header['columnIndex'] and headerRowIndex == header['rowIndex'] and header['content'] != '':
                columns.append(header)

    # fill attribute values
    for cell in cells:
        if cell['rowIndex'] == rowIndex:
            for column in columns:
                if column['columnIndex'] == cell['columnIndex']:
                    column_name = remove_line_breaks(column['content'])
                    node[column_name] = cell['content']

    # fill missing attributes with empty values
    for column in columns:
        column_name = remove_line_breaks(column['content'])
        if column_name not in node:
            node[column_name] = ''

''' check if items in a list are substrings of a string '''
def contains(content, list):
    for item in list:
        if item in content:
            return True
    return False

# this function checks if dictionary has a key without using exception handling
def has_key(dict, key):
    if key in dict:
        return True
    else:
        return False

''' rename duplicate headers '''
def rename_duplicate_headers(table):
    columns = {}
    for cell in table['cells']:
        content = cell['content']
        rowIndex = cell['rowIndex']
        columnIndex = cell['columnIndex']
        kind = cell['kind'] if 'kind' in cell else 'content' # (default)
        if kind == 'columnHeader':
            existing_column_index = get_item_value(columns, content)    
            if existing_column_index == '':
                occurrences = [(rowIndex, columnIndex)]
                columns[content] = occurrences
            elif (rowIndex, columnIndex) not in existing_column_index:
                existing_column_index.append((rowIndex, columnIndex))
    for cell in table['cells']:
        content = cell['content']
        rowIndex = cell['rowIndex']
        columnIndex = cell['columnIndex']
        kind = cell['kind'] if 'kind' in cell else 'content' # (default)
        if kind == 'columnHeader':
            existing_column_index = get_item_value(columns, content)
            for idx in range(len(existing_column_index)):
                if existing_column_index[idx][0] == rowIndex and existing_column_index[idx][1] == columnIndex:
                    break  
            if idx > 0:
                cell['content'] = cell['content'] + str(idx)
    return table

def truncate(string, n):
    string = string.replace('\n', ' ')
    if len(string) <= n:
        return string
    else:
        return string[:n-3] + '...'

''' validate node accordingly its attributes '''
def is_a_valid_node(node):
    # check each dictionary key
    ignore_values = ['n/a', '']
    for key in node:
        # check if the key is a valid attribute
        if key in RESERVED_ATTRIBUTES or node[key] in ignore_values:
            continue
        elif (key.startswith('TBD')):
            continue
        else:
            validation = azure_openai_utils.complete(VALIDATE_ATTRIBUTE_PROMPT, {'column_name': key, 'value': node[key]}).strip().lower()            
            invalid = True if validation == "invalid" else False
            if invalid:
                logger.debug(f"Invalid node '{truncate(node['content'],20)}'. Invalid value '{truncate(node[key],20)}' to '{truncate(key,20)}' column")
                return False
    return True

def get_node_styles(cell, document_styles):
    cell_styles = []
    for cell_span in cell['spans']:
        for style in document_styles:
            style_spans = style['spans'] if 'spans' in style else []
            for style_span in style_spans:
                if cell_span['offset'] == style_span['offset']:
                    cell_style = style.copy()
                    del cell_style['spans']
                    cell_styles.append(cell_style)
    return cell_styles

''' this function returns all document tables when tables are next to each other, they are merged into a single table '''
def load_tables(tables):
    _tables = []
    for table in tables:
        if len(_tables) == 0:
            _tables.append(table)
        else:
            last_table = _tables[-1]
            # check if it is the same table
            same_table = False
            last_bounding_region = last_table['boundingRegions'][-1]
            current_bounding_region = table['boundingRegions'][0]
            if last_bounding_region['pageNumber'] == current_bounding_region['pageNumber']:
                if last_bounding_region['polygon'][5] - current_bounding_region['polygon'][1] < 1.0:
                    same_table = True
            if same_table:
                # merge tables
                merged_table = last_table.copy()
                merged_table['rowCount'] = merged_table['rowCount'] + table['rowCount']
                merged_table['columnCount'] = max(merged_table['columnCount'],table['columnCount'])              

                # adjust current table cells before merge them
                for cell in table['cells']:
                    cell['rowIndex'] = cell['rowIndex'] + last_table['rowCount']
                    if 'kind' in cell: cell['kind'] = 'content' # changing current table headers to content

                # if column count is different add column span to the first cell and add 1 to the other cells
                difference = merged_table['columnCount'] - table['columnCount']
                if difference > 0:
                    # add to current table
                    for cell in table['cells']:
                        if cell['columnIndex'] == 0:
                            if 'columnSpan' in cell: 
                                cell['columnSpan'] = cell['columnSpan'] + abs(difference)
                            else:
                                cell['columnSpan'] = 1 + abs(difference)
                        else:
                            cell['columnIndex'] = cell['columnIndex'] + abs(difference)
                elif difference < 0:
                    # add to merged (last) table
                    for cell in merged_table['cells']:
                        if cell['columnIndex'] == 0:
                            if 'columnSpan' in cell: 
                                cell['columnSpan'] = cell['columnSpan'] + abs(difference)
                            else:
                                cell['columnSpan'] = 1 + abs(difference)
                        else:
                            cell['columnIndex'] = cell['columnIndex'] + abs(difference)
                merged_table['cells'] = merged_table['cells'] + table['cells']
                #TODO: adjust bounding regions, pages and spans
                _tables[-1] = merged_table
            else:
                _tables.append(table)

    return _tables



''' parse the json result and create the tree structure '''
def parse_json_result(data):
    trees = [] 
    # tables = data['tables']
    tables = load_tables(data['tables'])
    pages = data['pages']
    for idx, table in enumerate(tables):
        logger.debug(f"Parsing table {str(idx+1).zfill(3)}")
        table = rename_duplicate_headers(table)
        nodes = []
        headers = []
        parents_with_invalid_nodes = []
        for cell in table['cells']:
            content = cell['content']
            rowIndex = cell['rowIndex']
            columnIndex = cell['columnIndex']
            kind = cell['kind'] if 'kind' in cell else 'content' # (default)
            # identify headers to populate attributes later
            if kind == 'columnHeader':    
                headers.append({
                    'content': content,
                    'rowIndex': rowIndex,
                    'columnIndex': columnIndex
                })
            # identify content nodes               
            elif cell['columnIndex'] == 0 and len(cell['spans']) > 0 and not contains(cell['content'], IGNORE_ITEMS_LIST):
                node = {}
                node['content'] = cell['content']
                node['rowIndex'] = rowIndex
                node['span_offset'] = cell['spans'][0]['offset']
                node['span_length'] = cell['spans'][0]['length']
                node['styles'] = get_node_styles(cell, data['styles']) if 'styles' in data else []
                node['children'] = []

                # create new headers when needed to avoid tables with no header issue
                headers = add_missing_headers(table['cells'], headers, rowIndex, columnIndex)
                
                # populate nodes values 
                add_values(table['cells'], rowIndex, headers, node)
                
                # validate node before adding it to the tree
                valid_node = is_a_valid_node(node)

                parent = get_parent(pages, table, node['content'], node['rowIndex'], node['span_offset'], node['span_length'])
                if (valid_node):
                    if parent['content'] == 'Has no parent':
                        # root node
                        nodes.append(node)
                    else:
                        add_child(nodes, parent, node)
                elif parent['content'] != 'Has no parent':
                    parents_with_invalid_nodes.append(parent)

        trees.append(nodes)

    return trees

### Functions to convert tree structure to a dataframe ###

''' get the max height of the tree structure '''
def get_height(nodes):
    max_path = 0
    for node in nodes:
        if len(node['children']) > 0:
            max_path = max(max_path, get_height(node['children']))
    return max_path + 1

''' convert the tree structure to a list of items '''
def get_items_list(tree, curr_level, prefilled_item, levels, value_columns):
    list = []
    for node in tree:
        item = prefilled_item.copy()
        item[levels[curr_level]] = node['content']
        # add current item to the list (leaf node)
        for column in value_columns:
            try:
                item[column] = node[column]
            except KeyError:
                item[column] = ''
        # check if it isn't an empty row and has required columns
        if any(get_item_value(item, column) != '' for column in value_columns) and \
            all(get_item_value(item, column) != '' for column in MUST_HAVE_COLUMNS):
                list.append(item)
        else:
            logger.debug(f"Removing node '{truncate(node['content'],30)}'. It has no values")
        # process children
        if len(node['children']) > 0:
            list = list + get_items_list(node['children'], curr_level+1, item, levels, value_columns)
    return list

''' get tree first column name '''
def get_first_column_name(tree):
    first_column_name = ""
    first_element = tree[0]
    for key in first_element.keys():
        if first_element[key] == first_element['content'] and key != 'content':
            first_column_name = key
            break
    return first_column_name

def markdown_table(df):
    table = ""
    table = table + "|" + "|".join(df.columns) + "|\n"
    table = table + "|" + "|".join(["---" for _ in df.columns]) + "|\n"
    for i, row in df.iterrows():
        table = table + "|" + "|".join([str(val) for val in row]) + "|\n"
    return table

def infer_column_name(column, df):
    column_name = ""
    column_name = azure_openai_utils.complete(INFER_COLUMN_NAME_PROMPT, {'column_name': column, 'table': markdown_table(df)}).strip() 
    if column_name != "":
        logger.debug(f"Inferred '{column}' name as '{column_name}'")
    else:
        logger.debug(f"Could not infer '{column}' column name")        
        column_name = "Could not infer"   
    return column_name

''' this function remove columns that have no vale in a dataframe'''
def remove_empty_columns(df, columns):
    dataframe = df.copy()
    for column in dataframe.columns:
        if column in columns and dataframe[column].isnull().all():
            logger.debug(f"Removing column '{column}'. It has no values")
            dataframe.drop(column, axis=1, inplace=True)
    return dataframe

''' convert a tree to a dataframe '''	
def get_dataframe(tree):
    if len(tree) == 0: return pd.DataFrame()
    
    # create dataframe
    first_column_name = get_first_column_name(tree)
    levels = [first_column_name] + [first_column_name + str(i+1) for i in range(0, get_height(tree)-1)]
    value_columns = [column for column in tree[0].keys() if column not in levels + RESERVED_ATTRIBUTES]
    columns = levels + value_columns
    items_list = get_items_list(tree, 0, {}, levels, value_columns)
    df = pd.DataFrame(items_list, columns=columns)

    # clean levels columns with no value (may be generated by empty/invalid nodes)
    df = remove_empty_columns(df, levels)

    # infer TBD column names
    for column in columns:
        if column.startswith('TBD '):
            column_name = infer_column_name(column, df)
            df = df.rename(columns={column: column_name})
    
    return df