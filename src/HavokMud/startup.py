import HavokMud.stacklesssocket

# Monkeypatch in the 'stacklesssocket' module, so we get blocking sockets
# which are Stackless compatible.
HavokMud.stacklesssocket.install()

import gc
import logging
import os
import stackless

from HavokMud.config_loader import load_config_file
from HavokMud.database import Databases
from HavokMud.logging_support import logging_setup, logging_additional_setup
from HavokMud.server import Server
from HavokMud.settings import Settings

logger = logging.getLogger(__name__)

server_instance = None


def start_mud(loglevel=None, looping=False):
    if loglevel is None:
        loglevel = os.environ.get("HAVOKMUD_LOGGING", "INFO")
        loglevel = getattr(logging, loglevel)
    logging_setup(loglevel, console=True)

    config = load_config_file("config.json")
    if not config:
        return 1

    logging_additional_setup(config.get("loggingLevels", {}))

    if config.get("mud", {}).get("debug_gc", False):
        gc.set_debug(gc.DEBUG_STATS)

    profile = config.get("mud", {}).get("profile", None)
    if profile:
        os.environ["AWS_PROFILE"] = profile

    dbs = Databases(config)

    config = Settings.get_updated_config(dbs, config)

    bootstrapped = config.get("mud", {}).get("bootstrapped", False)
    if not bootstrapped:
        # Need to load in the bootstrap config file with default settings
        # to preseed the settings db.
        config.update(load_config_file("bootstrap.json"))
        config = Settings.get_updated_config(dbs, config)

    global server_instance
    if looping:
        try:
            server_instance = Server(config, dbs)
            while True:
                stackless.run()
        except KeyboardInterrupt:
            logger.info("Server manually stopped")
            # traceback.print_exc()
    else:
        server_instance = Server(config, dbs)

    return 0
