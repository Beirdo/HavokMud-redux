import json
import logging
import os

logger = logging.getLogger(__name__)

configDir = os.path.expanduser("~/.havokmud")


def load_config_file(filename):
    config_file = os.path.join(configDir, filename)
    try:
        with open(config_file) as f:
            config = json.load(f)
    except Exception:
        logger.critical("Could not load configuration file %s" % config_file)
        config = {}

    return config


def load_raw_file(filename):
    raw_file = os.path.join(configDir, filename)
    try:
        with open(raw_file) as f:
            data = f.read()
    except Exception:
        logger.critical("Could not load raw file %s" % raw_file)
        data = None

    return data
