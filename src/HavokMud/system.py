import logging

logger = logging.getLogger(__name__)


class System(object):
    name = None
    wallet_key = {}

    def __init__(self, name):
        self.name = name
