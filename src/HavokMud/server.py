import logging
import socket
import stackless
import traceback
import weakref
from threading import Lock

from HavokMud.account import Account
from HavokMud.config_loader import load_all_wallet_passwords
from HavokMud.connection import Connection
from HavokMud.dnslookup import DNSLookup
from HavokMud.encryption_helper import EncryptionEngine
from HavokMud.redis_handler import RedisHandler
from HavokMud.send_email import EmailHandler
from HavokMud.settings import Settings
from HavokMud.swaggerapi.eosio_chain import EOSChainAPI
from HavokMud.swaggerapi.eosio_wallet import EOSWalletAPI
from HavokMud.system import System

logger = logging.getLogger(__name__)


class Server(object):
    # These defaults are normally overwritten in the config file
    bindIp = "0.0.0.0"
    port = 3000
    wizlocked = False
    wizlock_reason = None
    profile = None

    def __init__(self, config, dbs, debug_mode=False):
        import HavokMud.startup

        HavokMud.startup.server_instance = self
        self.config = config

        self.__dict__.update(self.config.get("mud", {}))

        self.dbs = dbs
        self.user_lock = Lock()
        self.user_index = weakref.WeakValueDictionary()
        self.dns_lookup = DNSLookup()
        self.email_handler = EmailHandler(config)
        self.redis = RedisHandler(config)
        self.encryption = EncryptionEngine(config)
        self.wallet_api = EOSWalletAPI(config)
        self.chain_api = EOSChainAPI(config)

        stackless.schedule()

        # Need to load up self.system_wallet_passwords with encrypted wallet passwords
        system_wallets = {item.name: item for item in System.get_all_system_wallets()}
        wallet_passwords = {name: item.get_password() for (name, item) in system_wallets.items()}
        old_wallet_passwords = dict(wallet_passwords)
        wallet_passwords = load_all_wallet_passwords(wallet_passwords)
        logger.debug("Wallet passwords: %s" % wallet_passwords)

        self.system_wallets = system_wallets
        # Update/seed the wallets
        for (name, password) in wallet_passwords.items():
            if password != old_wallet_passwords.get(name, None):
                wallet = system_wallets.get(name, None)
                if wallet:
                    wallet.set_password(password)
                else:
                    wallet = System(name=name, password=password)
                wallet.save_to_db()
                wallet.prepare_wallet()

        self.domain = self.config.get("email", {}).get("domain", None)

        # Prime up the redis cache
        self.redis.do_command("delete", "userdb/*")
        self.redis.do_command("delete", "passdb/*")

        accounts = Account().get_all_accounts()
        for account in accounts:
            account.update_redis()

        if not debug_mode:
            stackless.tasklet(self.run)()

    def run(self):
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind((self.bindIp, self.port))
        logger.info("Listening on %s" % listen_socket.fileno())
        listen_socket.listen(10)

        logger.info("Accepting connections on %s:%s", self.bindIp, self.port)
        try:
            while True:
                try:
                    (clientSocket, clientAddress) = listen_socket.accept()
                    logger.info("Accepting on %s" % clientSocket.fileno())
                    Connection(clientSocket, clientAddress)
                except Exception as e:
                    logger.exception("Exception in accept loop")
                    pass
                stackless.schedule()
        except socket.error:
            traceback.print_exc()

    def register_user(self, user):
        with self.user_lock:
            self.user_index[id(user)] = user

    def unregister_user(self, user):
        with self.user_lock:
            self.user_index.pop(id(user), None)

    def list_users(self):
        with self.user_lock:
            return list(self.user_index.values())

    def is_wizlocked(self):
        return self.wizlocked

    def set_wizlock(self, value, reason):
        if value:
            self.wizlock_reason = reason

        self.wizlocked = value
