import logging
import stackless
from time import sleep

from HavokMud.currency import Currency
from HavokMud.database_object import DatabaseObject
from HavokMud.eosio.action import EOSAction
from HavokMud.eosio.permission import EOSPermission
from HavokMud.system import System
from HavokMud.wallet import Wallet, WalletType

logger = logging.getLogger(__name__)


class Bank(DatabaseObject):
    __fixed_fields__ = ["server", "tasklet", "wallets"]
    __database__ = None
    name = None

    def __init__(self, server=None, name=None, other=None):
        DatabaseObject.__init__(self)
        self.__real_class__ = self.__class__

        if other:
            self.__dict__.update(other.__dict__)
        else:
            if not server or not name:
                raise ValueError("Must specify server and name")
            self.server = server
            self.__database__ = self.server.dbs.bank_db
            self.name = name
            self.tasklet = None
            self.wallets = {}
            self.wallet_password = {}
            self.wallet_owner_key = {}
            self.wallet_active_key = {}
            self.wallet_keys = {}
            self.interest_rate = 0

    @staticmethod
    def load(server, name):
        bank = Bank(server, name)

        try:
            # if not in dynamo: will return with empty name field
            bank.load_from_db(name=name)

            if bank.name:
                wallet = Wallet.load(server, bank, WalletType.Stored)
                if wallet:
                    bank.wallets[WalletType.Stored] = wallet
                    return bank

            # New bank.  Wicked!  Let's create the wallets
            bank = Bank(server, name)
            bank.name = name
            bank.wallets[WalletType.Stored] = Wallet.create(server, bank, WalletType.Stored)
            # Set default interest rate to 10% (also saves to db)
            bank.set_interest_rate(10.0)
            return bank
        finally:
            bank.tasklet = stackless.tasklet(bank.calculate_interest_tasklet)()

    def deposit(self, player, currency: Currency):
        source: Wallet = player.wallets.get(WalletType.Carried, None)
        if not source:
            return False

        source.transfer_to(self, WalletType.Stored, currency)
        return True

    def get_balance(self, player) -> Currency:
        wallet: Wallet = player.wallets.get(WalletType.Carried, None)
        params = {
            "code": "banker",
            "table": "accounts",
            "scope": wallet.account_name,
        }
        result = self.server.chain_api.call("get_table_rows", **params)
        rows = result.get("rows", [])
        if not rows:
            return Currency()

        balance = " ".join(rows.get("balance", []))
        return Currency(coins=balance)

    def withdraw(self, player, currency: Currency):
        source: Wallet = self.wallets.get(WalletType.Stored, None)
        target: Wallet = player.wallets.get(WalletType.Carried, None)
        if not target or not source:
            return False

        with source.transaction() as transaction:
            auth = [EOSPermission(self.account_name, "active")]
            params = {
                "user": target.account_name,
                "amount": currency.convert_to_base()
            }
            action = EOSAction(self.server, "banker", "withdraw", auth, **params)
            transaction.add(action)

        return True

    def set_interest_rate(self, new_rate: float):
        new_rate = int(new_rate * 100.0)
        self.interest_rate = new_rate
        self.save_to_db()

        wallet: Wallet = self.wallets.get(WalletType.Stored, None)
        with wallet.transaction() as transaction:
            auth = [EOSPermission(System.account_name, "active")]
            params = {
                "rate": new_rate,
            }
            action = EOSAction(self.server, "banker", "setinterest", auth, **params)
            transaction.add(action)

    def calculate_interest_amounts(self):
        wallet: Wallet = self.wallets.get(WalletType.Stored, None)
        if not wallet:
            return

        with wallet.transaction() as transaction:
            auth = [EOSPermission(System.account_name, "active")]
            action = EOSAction(self.server, "banker", "calcinterest", auth)
            transaction.add(action)

    def calculate_interest_tasklet(self):
        while True:
            self.calculate_interest_amounts()
            sleep(3600.0)
