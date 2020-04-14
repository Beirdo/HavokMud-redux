import logging

logger = logging.getLogger(__name__)


class Bank(object):
    name = None

    def __init__(self, name):
        self.name = name
        self.wallet_password = {}
        self.wallet_owner_key = {}
        self.wallet_active_key = {}
        self.wallet_keys = {}
