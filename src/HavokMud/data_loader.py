import json
import logging
import os
import sys

logger = logging.getLogger(__name__)

baseDir = os.path.realpath(os.path.join(sys.argv[0], "..", ".."))
dataDir = os.path.join(baseDir, "data")


def load_data_file(filename):
    filename = os.path.join(dataDir, filename)
    try:
        with open(filename, "r") as f:
            data = json.load(f)
    except Exception:
        data = {}

    return data
