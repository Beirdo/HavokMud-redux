import logging

logger = logging.getLogger(__name__)


class Bank(object):
    name = None
    wallet_key = {}

    def __init__(self, name):
        self.name = name
