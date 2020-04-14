import logging

logger = logging.getLogger(__name__)


class System(object):
    name = None
    account_name = "mud.havokmud"

    def __init__(self, name):
        self.name = name
        self.wallet_password = {}
        self.wallet_owner_key = {}
        self.wallet_active_key = {}
        self.wallet_keys = {}
