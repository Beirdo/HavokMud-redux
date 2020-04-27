import json
import logging
import uuid
from threading import Lock

from HavokMud.database_object import DatabaseObject
from HavokMud.jinjaprocessor import jinja_processor
from HavokMud.logging_support import AccountLogMessage
from HavokMud.wallet import WalletType, Wallet

logger = logging.getLogger(__name__)


class Account(DatabaseObject):
    __fixed_fields__ = ["server", "connection", "hostname_lock", "player", "current_player",
                        "wallets"]
    __database__ = None

    def __init__(self, connection=None, email=None, password=None, other=None):
        DatabaseObject.__init__(self)
        self.__real_class__ = self.__class__

        if other:
            self.__dict__.update(other.__dict__)
            if not hasattr(self, "wallets") or not self.wallets:
                self.wallets = {}
            if not hasattr(self, "wallet_password") or not self.wallet_password:
                self.wallet_password = {}

            if not hasattr(self, "wallet_owner_key") or not self.wallet_owner_key:
                self.wallet_owner_key = {}

            if not hasattr(self, "wallet_active_key") or not self.wallet_active_key:
                self.wallet_active_key = {}

            if not hasattr(self, "wallet_keys") or not self.wallet_keys:
                self.wallet_keys = {}
        else:
            self.__database__ = self.server.dbs.account_db
            self.connection = connection
            self.hostname_lock = Lock()
            self.player = None
            self.current_player = None
            self.wallets = {}
            self.wallet_password = {}
            self.wallet_owner_key = {}
            self.wallet_active_key = {}
            self.wallet_keys = {}

            self.email = email
            self.password = password  # SHA512 digest
            self.new_password = None  # SHA512 digest
            self.ip_address = None
            self.hostname = None
            self.ansi_mode = False
            self.confcode = None
            self.confirmed = False
            self.players = []

    @staticmethod
    def lookup_by_email(connection, email):
        account = Account()

        # Look this up in DynamoDB
        # if not in dynamo: will return with empty email field
        account.load_from_db(email=email)
        if not account or not account.email:
            return Account()

        if not account.players:
            account.players = []

        account.wallets = {
            WalletType.Carried: Wallet.load(account, WalletType.Carried),
            WalletType.Stored: Wallet.load(account, WalletType.Stored),
        }

        if connection:
            account.connection = connection
            account.ip_address = connection.client_address[0]
            with account.hostname_lock:
                account.hostname = account.server.dns_lookup.do_reverse_dns(account.ip_address)
            connection.ansi_mode = account.ansi_mode
            connection.user.account = account
        return account

    @staticmethod
    def get_all_accounts():
        dummy = Account()
        return dummy.get_all()

    def send_confirmation_email(self):
        if not self.confcode:
            self.confcode = str(uuid.uuid4())
            self.save_to_db()

        logger.info(AccountLogMessage(self, "Sending confcode: %s" % self.confcode))

        # send an email with the confcode in it
        email_config = self.server.config.get("email", {})
        from_ = email_config.get("admin", None)
        domain = email_config.get("domain", None)
        if not from_ or not domain:
            logger.critical(AccountLogMessage(self, "Email not setup.  Aborting email send", _global=True))
            return
        from_ += "@" + domain

        kwargs = {
            "template": "confirmation_email.jinja",
            "params": {
                "server": self.server,
                "account": self,
            }
        }
        body = jinja_processor.process(kwargs)
        self.server.email_handler.send_email(from_, self.email, "Confirm your email for %s" % self.server.name,
                                             body_text=body)

    def is_sitelocked(self):
        # TODO
        # look up the connection's IP and hostname for possible bans
        return False

    def get_hostname(self):
        with self.hostname_lock:
            return self.hostname

    def update_redis(self):
        if not self.players:
            self.players = []

        for player in self.players:
            player = player.lower()
            user_item = {
                "user": "%s@%s" % (player, self.server.domain)
            }
            self.server.redis.do_command("set", "userdb/%s" % player, json.dumps(user_item))
            pass_item = {
                "password": "{PLAIN}%s" % self.password
            }
            self.server.redis.do_command("set", "passdb/%s" % player, json.dumps(pass_item))
