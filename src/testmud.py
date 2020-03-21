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
import logging
import os
import stackless

import HavokMud.stacklesssocket
# sys.modules["socket"] = stacklesssocket
from HavokMud.server import Server

# Monkeypatch in the 'stacklesssocket' module, so we get blocking sockets
# which are Stackless compatible.  This example code will avoid any use of
# the Stackless sockets except through normal socket usage.

HavokMud.stacklesssocket.install()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger("botocore").setLevel(logging.INFO)
    logging.getLogger("boto3").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.INFO)

    gc.set_debug(gc.DEBUG_STATS)

    try:
        env = os.environ.get("BUILD_MODE", "prod")
        testing = (env.lower() == "testing")
        Server("0.0.0.0", 3000, testing)  # use localstack for AWS resources in testing
        while True:
            stackless.run()
    except KeyboardInterrupt:
        logging.info("Server manually stopped")
        # traceback.print_exc()
