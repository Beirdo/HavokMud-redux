import base64
import hashlib
import logging
from contextlib import contextmanager
from enum import Enum

from HavokMud.currency import Currency, coin_names
from HavokMud.eosio.action import EOSAction
from HavokMud.eosio.permission import EOSPermission
from HavokMud.eosio.transaction import EOSTransaction
from HavokMud.settings import Settings
from HavokMud.system import System

logger = logging.getLogger(__name__)


class WalletError(Exception):
    pass


class WalletType(Enum):
    Carried = 1
    Stored = 2
    Supply = 3
    System = 4


class Wallet(object):
    prefix_map = {
        "Account": "a.",
        "Player": "p.",
        "NPCPlayer": "n.",
        "Bank": "b.",
    }

    name_map = {
        "Account": "email",
        "Player": "name",
        "NPCPlayer": "name",
        "Bank": "name",
        "System": "name",
    }

    account_wallet_info_map = {}

    def __init__(self, owner=None, wallet_type: WalletType = None):
        from HavokMud.startup import server_instance
        self.server = server_instance
        self.owner = owner
        self.wallet_type = wallet_type
        self.tokens = list(coin_names)
        self.password = None
        self.active_key = {}
        self.keys = {}
        self.wallet_name = None
        self.account_name = None
        self.balance = None

    def deposit(self, currency: Currency):
        # New funds, these come from the economy as new coins
        system_wallet = Wallet.load(self.server, account_name=System.account_name)
        return system_wallet.transfer_to(self.owner, self.wallet_type, currency)

    def withdraw(self, currency):
        # These funds are spent, and are returned to the economy
        system_wallet = Wallet.load(self.server, account_name=System.account_name)
        return self.transfer_to(System(), WalletType.Supply, currency)

    def transfer_in(self, from_wallet, currency):
        # These funds are transferred in from another wallet
        return from_wallet.transfer_to(self.owner, self.wallet_type, currency)

    def transfer_out(self, to_wallet, currency):
        # These funds are transferred out to another wallet
        return self.transfer_to(to_wallet.owner, to_wallet.wallet_type, currency)

    def get_balance(self):
        # Returns the current balance as a currency object
        currency = Currency()
        for token in self.tokens:
            try:
                params = {
                    "code": "eosio.token",
                    "account": self.account_name,
                    "symbol": token,
                }
                balance = self.server.chain_api.call("get_currency_balance", **params)
                currency.add_tokens(balance)
            except Exception as e:
                pass

        self.balance = currency
        return currency

    @staticmethod
    def create(owner, wallet_type):
        from HavokMud.startup import server_instance
        server = server_instance

        # Create a new wallet
        wallet_info = Wallet._hash_wallet_name(owner, wallet_type)
        wallet_name = wallet_info.get("wallet_name", None)
        account_name = wallet_info.get("account_name", None)
        logger.info("Wallet Info: %s" % wallet_info)

        try:
            password = server.wallet_api.call("create", wallet_name)
        except Exception as e:
            logger.error("Couldn't create wallet %s: %s" % (wallet_name, e))
            return None

        wallet = Wallet(owner, wallet_type)
        wallet.wallet_name = wallet_name
        wallet.account_name = account_name
        wallet.password = server.encryption.encrypt_string(password)

        try:
            owner_key = server.wallet_api.call("create_key", wallet_name, "")
            logger.info("Created new owner public key %s for %s" % (owner_key, wallet_name))
        except Exception as e:
            logger.error("Couldn't create a key in wallet %s: %s" % (wallet_name, e))
            return None

        try:
            active_key = server.wallet_api.call("create_key", wallet_name, "")
            logger.info("Created new active public key %s for %s" % (active_key, wallet_name))
        except Exception as e:
            logger.error("Couldn't create a key in wallet %s: %s" % (wallet_name, e))
            return None

        wallet.active_key[str(wallet_type)] = active_key

        owner.wallet_password[str(wallet_type)] = wallet.password
        owner.wallet_owner_key[str(wallet_type)] = owner_key
        owner.wallet_active_key[str(wallet_type)] = active_key
        owner.save_to_db()

        # List all keys in the wallet (must be unlocked)
        wallet._list_keys()

        # Now lock the wallet
        try:
            server.wallet_api.call("lock", wallet_name)
        except Exception as e:
            logger.error("Couldn't lock wallet %s: %s" % (wallet_name, e))
            return None

        # Need to create the account on the blockchain.  This requires a specific
        # transaction to be created.
        system_account_name = System.account_name
        with wallet.transaction() as transaction:
            params = {
                "creator": system_account_name,
                "name": account_name,
                "owner": {
                    "threshold": 1,
                    "keys": [{
                        "key": owner_key,
                        "weight": 1
                    }],
                    "accounts": [],
                    "waits": []
                },
                "active": {
                    "threshold": 1,
                    "keys": [{
                        "key": active_key,
                        "weight": 1
                    }],
                    "accounts": [],
                    "waits": []
                }
            }
            auth = [EOSPermission(system_account_name, "active")]
            transaction.add(EOSAction("eosio", "newaccount", auth, **params))

            # Need to buy some RAM
            params = {
                "payer": system_account_name,
                "receiver": account_name,
                "bytes": 8192
            }
            auth = [EOSPermission(system_account_name, "active")]
            transaction.add(EOSAction("eosio", "buyrambytes", auth, **params))

            # And need to delegate CPU and NET
            params = {
                "from": system_account_name,
                "receiver": account_name,
                "stake_net_quantity": "1.0000 SYS",
                "stake_cpu_quantity": "1.0000 SYS",
                "transfer": False
            }
            auth = [EOSPermission(system_account_name, "active")]
            transaction.add(EOSAction("eosio", "delegatebw", auth, **params))

        return wallet

    def transfer_to(self, target, wallet_type: WalletType, currency: Currency):
        with self.transaction() as transaction:
            return self._transaction_transfer_to(transaction, target, wallet_type, currency)
        self.get_balance()

    def _transaction_transfer_to(self, transaction: EOSTransaction, target, wallet_type: WalletType,
                                 currency: Currency, pending_payment: Currency = None,
                                 break_coins: bool = False):

        target_info = Wallet._hash_wallet_name(target, wallet_type)
        target_account = target_info.get("account_name", None)
        if not target_account:
            raise WalletError("Can't transfer to an unknown account")

        self.get_balance()

        balance = Currency(currency=self.balance)
        if pending_payment:
            balance.add_value(pending_payment)

        try:
            if break_coins:
                (from_system, payment) = balance.break_coins_payment(currency)
            else:
                payment = balance.minimal_payment(currency)
                from_system = Currency()
        except Exception as e:
            raise WalletError("Can't transfer %s: %s" % (currency, e))

        for (count, token) in payment.get_as_tokens():
            self._transfer_tokens(transaction, target_account, count, token)

        if from_system:
            system_wallet: Wallet = Wallet.load(self.server, account_name=System.account_name)
            for (count, token) in from_system.get_as_tokens():
                if count > 0:
                    system_wallet._transfer_tokens(transaction, self.account_name, count, token)
                elif count < 0:
                    self._transfer_tokens(transaction, System.account_name, -count, token)

        change = currency.subtract_value(payment)
        if not change.is_zero():
            target_wallet = Wallet.load(account_name=target_account)
            if not target_wallet:
                target_wallet = Wallet.create(target, wallet_type)
                if not target_wallet._transaction_transfer_to(transaction, self.owner, self.wallet_type, change,
                                                              pending_payment=payment):
                    target_wallet._transaction_transfer_to(transaction, self.owner, self.wallet_type, change,
                                                           pending_payment=payment, break_coins=True)

        return change.is_zero()

    def _transfer_tokens(self, transaction: EOSTransaction, target_account_name: str, count: int, token: str,
                         memo: str):
        params = {
            "from": self.account_name,
            "to": target_account_name,
            "quantity": "%.4f %s" % (count, token),
            "memo": transaction.memo,
        }
        auth = [EOSPermission(self.account_name, "active")]
        action = EOSAction("eosio.token", "transfer", auth, **params)
        transaction.add(action)

    @staticmethod
    def load(owner=None, wallet_type=None, account_name=None):
        from HavokMud.startup import server_instance
        server = server_instance

        wallet_info = None
        if account_name:
            wallet_info = Wallet.account_wallet_info_map.get(account_name, None)
            if not wallet_info:
                owner = server.system_wallets.get(account_name, None)
                if not owner:
                    raise WalletError("Wallet %s not yet created" % account_name)
                wallet_info = Wallet._hash_wallet_name(owner, WalletType.System)
        elif owner is not None and wallet_type is not None:
            # Load up a wallet based on owner and type of wallet.  If there is no wallet
            # yet, return None, and the caller should use create()
            wallet_info = Wallet._hash_wallet_name(owner, wallet_type)
            if not wallet_info:
                raise WalletError("Wallet mapping error")

        if not wallet_info:
            raise WalletError("No identifying parameters given")

        wallet_name = wallet_info.get("wallet_name", None)
        owner = wallet_info.get("owner", None)
        wallet_type = wallet_info.get("wallet_type", None)

        try:
            server.wallet_api.call("open", wallet_name)
        except Exception as e:
            logger.error("Couldn't load wallet %s: %s" % (wallet_name, e))
            return None

        wallet = Wallet(owner, wallet_type)
        wallet.wallet_name = wallet_name
        wallet.account_name = account_name

        # Keep encrypted until needed
        wallet.password = owner.wallet_password.get(str(wallet_type), None)
        password = server.encryption.decrypt_string(wallet.password)

        try:
            server.wallet_api.call("unlock", wallet_name, password)
        except Exception as e:
            logger.error("Couldn't unlock wallet %s: %s" % (wallet_name, e))
            raise e

        wallet._list_keys()

        try:
            server.wallet_api.call("lock", wallet_name)
        except Exception as e:
            logger.error("Couldn't lock wallet %s: %s" % (wallet_name, e))
            raise e

        return wallet

    def _list_keys(self):
        # Must be unlocked
        password = self.server.encryption.decrypt_string(self.password)

        keys = dict(self.owner.wallet_keys.get(str(self.wallet_type), {}))
        try:
            new_keys = self.server.wallet_api.call("list_keys", self.wallet_name, password)
        except Exception as e:
            logger.error("Couldn't list keys for owner %s, type %s: %s" % (self.wallet_name, self.wallet_type, e))
            new_keys = []

        # logger.debug("raw keys: %s" % new_keys)
        # Keep our private keys encrypted in memory until they are needed
        new_keys = {public: self.server.encryption.encrypt_string(private)
                    for (public, private) in new_keys}
        # logger.debug("old_keys: %s" % keys)
        # logger.debug("new_keys: %s" % new_keys)

        keys.update(new_keys)
        self.owner.wallet_keys[str(self.wallet_type)] = keys
        self.owner.save_to_db()

        self.keys = keys

    def destroy(self):
        # The wallet's contents will be transferred to the economy if any value to
        # be found
        self.get_balance()
        with self.transaction() as transaction:
            self._transaction_transfer_to(transaction, System(), WalletType.Supply, self.balance())

    def _load_wallet_password(self):
        setting = Settings.lookup_by_key("wallet_password")
        password = self.server.encryption.decrypt_string(setting)
        return password

    @staticmethod
    def _hash_wallet_name(owner, wallet_type: WalletType):
        klass = owner.__class__.__name__
        names = list(map(lambda x: x[1], filter(lambda x: klass == x[0], Wallet.name_map.items())))
        if not names:
            name = "unknown"
        else:
            attrib = names[0]
            name = getattr(owner, attrib, "unknown")
        if not name:
            name = "unknown"

        if wallet_type == WalletType.System:
            wallet_name = name
            account_name = name
        else:
            wallet_name = ".".join([klass, name, wallet_type.name])
            wallet_name = wallet_name.replace(" ", "_")

            # EOSIO account names are 12 bytes long, start with a letter, and contain:
            # [a-z], [1-5], "."

            # We need a 10 character string.  Use Blake2b to get a 6-byte hash
            full_hash = hashlib.blake2b(wallet_name.encode("utf-8"), digest_size=6, key=b"HavokMud:wallet")

            # Convert the 6 byte hash into 16 byte encoding (base32), and strip off the padding
            # giving us 10 bytes, which we want lower case, not upper
            encoded = base64.b32encode(full_hash.digest()).decode("utf-8").lower()[:10]

            # Base32 does [A-Z], [2-7], so translate all "6" to "1", and all "7" to "."
            encoded = encoded.replace("6", "1")
            encoded = encoded.replace("7", ".")
            # Can't end an account name with a ".", so let's remove it
            encoded = encoded.rstrip(".")

            prefixes = list(
                map(lambda x: x[1], filter(lambda x: owner.__class__.__name__ == x[0], Wallet.prefix_map.items())))
            if not prefixes:
                prefixes = ["x."]
            prefix = prefixes[0]

            account_name = prefix + encoded

        wallet_info = {
            "account_name": account_name,
            "wallet_name": wallet_name,
            "full_name": wallet_name,
            "owner": owner,
            "wallet_type": wallet_type,
        }

        # keosd will refuse @, so let's use the encoded name for the wallet_name
        if klass == "Account":
            wallet_info["wallet_name"] = account_name

        Wallet.account_wallet_info_map[account_name] = wallet_info

        return wallet_info

    @contextmanager
    def transaction(self):
        transaction = EOSTransaction()
        try:
            yield transaction
        except Exception as e:
            logger.exception("Exception while generating transaction: %s" % e)
            transaction = None
        finally:
            if transaction and transaction.actions:
                transaction.send()
