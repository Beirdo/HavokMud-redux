import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

dataDir = os.path.join(os.getcwd(), "data")


def load_data_file(filename):
    filename = os.path.join(dataDir, filename)
    try:
        with open(filename, "r") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Exception while loading data: %s" % e)
        data = {}

    return data
