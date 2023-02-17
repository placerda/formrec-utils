import re
import pandas as pd

## General functions ##
''' return empty string if the item is not found in a collection '''
def get_item_value(item, column):
    try:
        return item[column]
    except KeyError:
        return ''


### Functions to create items in tree structure (sub-group hierarchy) ###

THRESHOLD = 0.05 # Fine tune the indent size accordingly the documents used.
IGNORE_ITEMS_LIST = [] # Ignore these items when creating the tree structure. Example IGNORE_ITEMS_LIST = ["Subtotal", "Total"]
MUST_HAVE_COLUMNS = [] # Must have these columns filled to be included in the dataframe. Example: MUST_HAVE_COLUMNS = ["Impl"]

''' get the x coordinate of a cell '''
def get_x(pages, content, span_offset, span_length):
    x = 0
    for page in pages:
        lines = page.lines
        for line in lines:
            if line.content in content and line.spans[0].offset == span_offset: # and line.spans[0].length == span_length:
                x = line.polygon[0].x
                break
    return x

''' get the immediate parent of a cell '''
def get_parent(pages, table, content, rowIndex, span_offset, span_length):
    child_x = get_x(pages, content, span_offset, span_length)
    parent = {'content': "Has no parent", 'rowIndex': -1, 'span_offset': 0, 'span_length': 0}
    for cell in table.cells:
        # check each cell as a candidate parent, check it to confirm.
        candidate = {
            'content': cell.content,
            'rowIndex': cell.row_index,
            'columnIndex': cell.column_index,
            'kind': cell.kind
        }
        if candidate['columnIndex'] == 0 and candidate['kind'] == 'content' and len(cell.spans) > 0:
            candidate['span_offset'] = cell.spans[0].offset
            candidate['span_length'] = cell.spans[0].length            
            candidate_x = get_x(pages, candidate['content'], candidate['span_offset'] , candidate['span_length'])
            if child_x - candidate_x > THRESHOLD:
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
            item['childs'].append(node)
            break
        else:
            add_child(item['childs'], parent, node)

''' remove line breaks from a string '''
def remove_line_breaks(content):
    return re.sub('\n', ' ', content).strip()

''' populate the node with attribute values '''
def add_values(cells, rowIndex, headers, node):
    # find number of columns
    num_columns = 0
    for header in headers:
        if header['columnIndex'] > num_columns:
            num_columns = header['columnIndex']

    columns = []

    # find header row by looking for the closest header above the current row for each column
    for column_i in range(0, num_columns):
        current_distance = 1000000
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
        if cell.row_index == rowIndex:
            for column in columns:
                if column['columnIndex'] == cell.column_index:
                    column_name = remove_line_breaks(column['content'])
                    node[column_name] = cell.content

''' check if items in a list are substrings of a string '''
def contains(content, list):
    for item in list:
        if item in content:
            return True
    return False

''' rename duplicate columns '''
def rename_duplicate_columns(table):
    columns = {}
    for cell in table.cells:
        content = cell.content
        rowIndex = cell.row_index
        columnIndex = cell.column_index
        kind = cell.kind
        if kind == 'columnHeader':
            existing_column_index = get_item_value(columns, content)    
            if existing_column_index == '':
                occurrences = [(rowIndex, columnIndex)]
                columns[content] = occurrences
            elif (rowIndex, columnIndex) not in existing_column_index:
                existing_column_index.append((rowIndex, columnIndex))
    for cell in table.cells:
        content = cell.content
        rowIndex = cell.row_index
        columnIndex = cell.column_index
        kind = cell.kind
        if kind == 'columnHeader':
            existing_column_index = get_item_value(columns, content)
            for idx in range(len(existing_column_index)):
                if existing_column_index[idx][0] == rowIndex and existing_column_index[idx][1] == columnIndex:
                    break  
            if idx > 0:
                cell.content = cell.content + str(idx)
    return table

''' parse the json result and create the tree structure '''
def parse_json_result(data):
    trees = []
    pages = data.pages
    tables = data.tables    
    for table in tables:
        table = rename_duplicate_columns(table)
        nodes = []
        headers = []
        for cell in table.cells:
            content = cell.content,
            rowIndex = cell.row_index
            columnIndex = cell.column_index
            kind = cell.kind
            # identify headers to populate attributes later
            if kind == 'columnHeader':    
                headers.append({
                    'content': content[0],
                    'rowIndex': rowIndex,
                    'columnIndex': columnIndex
                })
            # identify content nodes               
            elif cell.column_index == 0 and len(cell.spans) > 0 and not contains(cell.content, IGNORE_ITEMS_LIST):
                node = {}
                node['content'] = cell.content
                node['rowIndex'] = rowIndex
                node['span_offset'] = cell.spans[0].offset
                node['span_length'] = cell.spans[0].length
                node['childs'] = []

                # populate nodes values 
                add_values(table.cells, rowIndex, headers, node)
                
                parent = get_parent(pages, table, node['content'], node['rowIndex'], node['span_offset'], node['span_length'])
                if parent['content'] == 'Has no parent':
                    # root node
                    nodes.append(node)
                else:
                    add_child(nodes, parent, node)
        trees.append(nodes)
    return trees


### Functions to convert tree structure to a dataframe ###

''' get the max height of the tree structure '''
def get_height(nodes):
    max_path = 0
    for node in nodes:
        if len(node['childs']) > 0:
            max_path = max(max_path, get_height(node['childs']))
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
        # check if it has required columns then append to the list
        if all(get_item_value(item, column) != '' for column in MUST_HAVE_COLUMNS):
            list.append(item)
        if len(node['childs']) > 0:
            list = list + get_items_list(node['childs'], curr_level+1, item, levels, value_columns)
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

''' convert a tree to a dataframe '''	
def get_dataframe(tree):
    if len(tree) == 0: return pd.DataFrame()
    first_column_name = get_first_column_name(tree)
    levels = [first_column_name] + [first_column_name + str(i+1) for i in range(0, get_height(tree)-1)]
    control_attributes = ['content', 'rowIndex', 'span_offset', 'span_length', 'childs']
    value_columns = [column for column in tree[0].keys() if column not in levels + control_attributes]
    columns = levels + value_columns
    items_list = get_items_list(tree, 0, {}, levels, value_columns)    
    df = pd.DataFrame(items_list, columns=columns)
    return df