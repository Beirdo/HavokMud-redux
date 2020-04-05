import logging
import socket
import stackless
import traceback
import weakref
from threading import Lock

from HavokMud.account import Account
from HavokMud.connection import Connection
from HavokMud.database import Databases
from HavokMud.dnslookup import DNSLookup
from HavokMud.encryption_helper import EncryptionEngine
from HavokMud.redis_handler import RedisHandler
from HavokMud.send_email import EmailHandler

logger = logging.getLogger(__name__)


class Server(object):
    # These defaults are normally overwritten in the config file
    bindIp = "0.0.0.0"
    port = 3000
    wizlocked = False
    wizlock_reason = None

    def __init__(self, config):
        self.config = config
        self.__dict__.update(self.config.get("mud", {}))

        self.user_lock = Lock()
        self.user_index = weakref.WeakValueDictionary()
        self.dbs = Databases(self.config)
        self.dns_lookup = DNSLookup()
        self.email_handler = EmailHandler(config)
        self.redis = RedisHandler(config)
        self.encryption = EncryptionEngine(config)

        stackless.schedule()

        self.domain = self.config.get("email", {}).get("domain", None)

        # Prime up the redis cache
        self.redis.do_command("delete", "userdb/*")
        self.redis.do_command("delete", "passdb/*")
        accounts = Account.get_all_accounts(self)
        for account in accounts:
            account.update_redis()

        stackless.tasklet(self.run)()

    def run(self):
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind((self.bindIp, self.port))
        logger.info("Listening on %s" % listen_socket.fileno())
        listen_socket.listen(5)

        logger.info("Accepting connections on %s %s", self.bindIp, self.port)
        try:
            while True:
                try:
                    (clientSocket, clientAddress) = listen_socket.accept()
                    logger.info("Accepting on %s" % clientSocket.fileno())
                    Connection(self, clientSocket, clientAddress)
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
