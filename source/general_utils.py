"""
Title: General Utility Functions
Author: Paulo Lacerda
Description: Utility functions to use in other scripts

"""
import logging

## LOGGER CONFIGURATION ##
logger = logging.getLogger('formrec-utils')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
