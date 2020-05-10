import logging

from HavokMud.database_object import DatabaseObject

logger = logging.getLogger(__name__)


class System(DatabaseObject):
    __fixed_fields__ = ["account_name", "wallets", "wallet_type"]
    __database__ = None

    name = "System"
    account_name = "mud.havokmud"

    def __init__(self, name=None, password=None, other=None):
        DatabaseObject.__init__(self)
        self.__real_class__ = self.__class__

        if other:
            self.__dict__.update(other.__dict__)
            if not hasattr(self, "wallets") or not self.wallets:
                self.wallets = {}
        else:
            self.__database__ = self.server.dbs.system_db

            if name:
                self.name = name
            self.wallet_password = {}
            self.wallet_owner_key = {}
            self.wallet_active_key = {}
            self.wallet_keys = {}
            self.wallets = {}

            from HavokMud.wallet import WalletType
            self.wallet_type = str(WalletType.System)

            if not name or not password:
                return

            self.wallet_password[self.wallet_type] = password

    def get_password(self):
        return self.wallet_password.get(self.wallet_type, None)

    def set_password(self, password):
        self.wallet_password[self.wallet_type] = password

    @staticmethod
    def lookup_by_name(name):
        system = System()

        # Look this up in DynamoDB
        # if not in dynamo: will return with empty email field
        system.load_from_db(name=name)
        if not system or not system.name:
            return System()

        system.prepare_wallet()
        return system

    def prepare_wallet(self):
        from HavokMud.wallet import WalletType, Wallet
        self.wallets = {}
        for type_ in [WalletType.System]:
            wallet = Wallet.load(self, type_)
            if not wallet:
                raise KeyError("System wallet %s doesn't exist!" % self.name)
            self.wallets[str(type_)] = wallet

    @staticmethod
    def get_all_system_wallets():
        dummy = System()
        wallets = dummy.get_all()
        for wallet in wallets:
            wallet.prepare_wallet()
        return wallets
