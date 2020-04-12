import base64
import hashlib
import logging

from HavokMud.account import Account
from HavokMud.bank import Bank
from HavokMud.currency import Currency
from HavokMud.npcplayer import NPCPlayer
from HavokMud.player import Player
from HavokMud.settings import Settings
from HavokMud.system import System

logger = logging.getLogger(__name__)


class Wallet(object):
    prefix_map = {
        Account, "a.",
        Player, "p.",
        NPCPlayer, "n.",
        Bank, "b.",
        System, "s.",
    }

    name_map = {
        Account, "email",
        Player, "name",
        NPCPlayer, "name",
        Bank, "name",
        System, "name",
    }

    tokens = Currency.

    def __init__(self, server, owner=None, wallet_type=None):
        self.server = server
        self.owner = owner
        self.wallet_type = wallet_type
        self.password = None
        self.keys = {}
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
    def create(server, owner, wallet_type):
        # Create a new wallet
        name = Wallet._hash_wallet_name(owner, wallet_type)

        try:
            password = server.wallet_api.call("create", name)
        except Exception as e:
            logger.error("Couldn't create wallet %s: %s" % (name, e))
            return None

        wallet = Wallet(server, owner, wallet_type)
        wallet.name = name
        wallet.password = server.encryption.encrypt(password)

        try:
            publicKey = server.wallet_api.call("create_key", name, "")
            logger.info("Created new public key %s for %s" % (publicKey, name))
        except Exception as e:
            logger.error("Couldn't create a key in wallet %s: %s" % (name, e))
            return None

        try:
            server.wallet_api.call("lock", name);
        except Exception as e:
            logger.error("Couldn't lock wallet %s: %s" % (name, e))
            return None

        wallet._list_keys()
        return wallet

    @staticmethod
    def load(server, owner, wallet_type):
        # Load up a wallet based on owner and type of wallet.  If there is no wallet
        # yet, return None, and the caller should use create()
        name = Wallet._hash_wallet_name(owner, wallet_type)
        try:
            server.wallet_api.call("open", name)
        except Exception as e:
            logger.error("Couldn't load wallet %s: %s" % (name, e))
            return None

        wallet = Wallet(server, owner, wallet_type)
        wallet.name = name
        # Keep encrypted until needed
        wallet.password = owner.wallet_password.get(wallet_type, None)
        wallet._list_keys()
        return wallet

    def _list_keys(self):
        password = self.server.encryption.decrypt(self.password)

        keys = self.owner.wallet_keys.get(self.wallet_type, {})
        try:
            new_keys = self.server.wallet_api.call("list_keys", self.name, password)
        except Exception as e:
            logger.error("Couldn't list keys for owner %s, type %s: %s" % (self.name, self.wallet_type, e))
            new_keys = {}

        # Keep our private keys encrypted in memory until they are needed
        new_keys = {public: self.server.encryption.encrypt(private) for (public, private) in new_keys.items()}
        old_keys = keys

        keys.update(new_keys)
        if keys != old_keys:
            self.owner.wallet_keys[self.wallet_type] = keys
            self.owner.save_to_db()

        self.keys = keys

    def destroy(self):
        # The wallet's contents will be transferred to the economy if any value to
        # be found, and then the wallet destroyed (removed from the system)
        pass

    def _load_wallet_password(self):
        setting = Settings.lookup_by_key(self.server, "wallet_password")
        password = self.server.encryption.decrypt(setting)
        return password

    @staticmethod
    def _hash_wallet_name(owner, wallet_type):
        names = list(map(lambda x: x[1], filter(lambda x: isinstance(owner, x[0]), Wallet.name_map.items())))
        if not names:
            name = "unknown"
        else:
            attrib = names[0]
            name = getattr(owner, attrib, "unknown")
        base = ":".join([name, str(wallet_type)])

        # EOSIO account names are 12 bytes long, start with a letter, and contain:
        # [a-z], [1-5], "."

        # We need a 10 character string.  Use Blake2b to get a 6-byte hash
        full_hash = hashlib.blake2b(base.encode("utf-8"), digest_size=6, key=b"HavokMud:wallet")

        # Convert the 6 byte hash into 16 byte encoding (base32), and strip off the padding
        # giving us 10 bytes, which we want lower case, not upper
        encoded = base64.b32encode(full_hash.digest()).decode("utf-8").lower()[:10]

        # Base32 does [A-Z], [2-7], so translate all "6" to "1", and all "7" to "."
        encoded.replace("6", "1")
        encoded.replace("7", ".")

        prefixes = list(map(lambda x: x[1], filter(lambda x: isinstance(owner, x[0]), Wallet.prefix_map.items())))
        if not prefixes:
            prefixes = ["x."]
        prefix = prefixes[0]

        return prefix + encoded
