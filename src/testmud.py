#! /usr/bin/env python

#
# A very simple MUD server based on the Stackless compatible sockets.
#
# Author: Richard Tew <richard.m.tew@gmail.com>
#
# This code was written to serve as an example of Stackless Python usage.
# Feel free to email me with any questions, comments, or suggestions for
# improvement.
#
import gc
import json
import logging
import os
import stackless
import sys

import HavokMud.stacklesssocket
from HavokMud.server import Server

logger = logging.getLogger(__name__)

# Monkeypatch in the 'stacklesssocket' module, so we get blocking sockets
# which are Stackless compatible.
HavokMud.stacklesssocket.install()

if __name__ == "__main__":
    format = '%(asctime)s %(levelname)s [PID %(process)d] (%(name)s:%(lineno)d) %(message)s'
    logging.basicConfig(level=logging.DEBUG, format=format)

    configDir = os.path.expanduser("~/.havokmud")
    configFile = os.path.join(configDir, "config.json")
    try:
        with open(configFile) as f:
            config = json.load(f)
    except Exception:
        logger.critical("Could not load configuration file %s" % configFile)
        logger.exception("Exception stack:")
        sys.exit(1)

    loggingConfig = config.get("loggingLevels", {})
    for (module, levelname) in loggingConfig.items():
        logging.getLogger(module).setLevel(getattr(logging, levelname, "DEBUG"))

    if config.get("mud", {}).get("debug_gc", False):
        gc.set_debug(gc.DEBUG_STATS)

    try:
        Server(config)
        while True:
            stackless.run()
    except KeyboardInterrupt:
        logger.info("Server manually stopped")
        # traceback.print_exc()
