import logging

logger = logging.getLogger(__name__)


class Wallet(object):
    def __init__(self, owner=None):
        self.owner = owner
        self.key = None
        self.wallet_type = None
        self.name = None

    def deposit(self, currency):
        # New funds, these come from the economy as new coins
        pass

    def withdraw(self, currency):
        # These funds are spent, and are returned to the economy
        pass

    def transfer_in(self, from_wallet, currency):
        # These funds are transferred in from another wallet
        pass

    def transfer_out(self, to_wallet, currency):
        # These funds are transferred out to another wallet
        pass

    def get_balance(self):
        # Returns the current balance as a currency object
        pass

    @staticmethod
    def create(owner, wallet_type):
        # Create a new wallet
        pass

    @staticmethod
    def load(owner, wallet_type):
        # Load up a wallet based on owner and type of wallet.  If there is no wallet
        # yet, return None, and the caller should use create()
        pass

    def destroy(self):
        # The wallet's contents will be transferred to the economy if any value to
        # be found, and then the wallet destroyed (removed from the system)
        pass
