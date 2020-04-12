import logging

logger = logging.getLogger(__name__)


class NPCPlayer(object):
    name = None
    wallet_key = {}

    def __init__(self, name):
        self.name = name
