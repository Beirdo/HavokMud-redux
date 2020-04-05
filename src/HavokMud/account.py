import json
import logging
import uuid
from threading import Lock

from HavokMud.database_object import DatabaseObject
from HavokMud.jinjaprocessor import jinja_processor

logger = logging.getLogger(__name__)


class Account(DatabaseObject):
    __fixed_fields__ = ["server", "connection", "hostname_lock", "player", "current_player"]
    __database__ = None

    def __init__(self, server, connection, email=None, password=None):
        DatabaseObject.__init__(self)
        self.server = server
        self.__database__ = self.server.dbs.account_db
        self.connection = connection
        self.hostname_lock = Lock()
        self.player = None
        self.current_player = None

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
    def lookup_by_email(server, connection, email):
        # Look this up in DynamoDB
        account = Account(server, connection, email)

        if connection:
            connection.ansi_mode = account.ansi_mode

        # if not in dynamo: will return with empty email field
        account.load_from_db(email=email)

        if connection:
            account.ip_address = connection.client_address[0]
            with account.hostname_lock:
                account.hostname = server.dns_lookup.do_reverse_dns(account.ip_address)
            connection.ansi_mode = account.ansi_mode
        return account

    @staticmethod
    def get_all_accounts(server):
        return [Account(server, None, email=item.get("email", None), password=item.get("password", None))
                for item in server.dbs.account_db.get_all()]

    def send_confirmation_email(self):
        if not self.confcode:
            self.confcode = str(uuid.uuid4())
            self.save_to_db()

        # send an email with the confcode in it
        email_config = self.server.config.get("email", {})
        from_ = email_config.get("admin", None)
        domain = email_config.get("domain", None)
        if not from_ or not domain:
            logger.critical("Email not setup.  Aborting email send")
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
        for player in self.players:
            player = player.lower()
            userItem = {
                "user": "%s@%s" % (player, self.server.domain)
            }
            self.server.redis.do_command("set", "userdb/%s" % player, json.dumps(userItem))
            passItem = {
                "password": "{PLAIN}%s" % self.password
            }
            self.server.redis.do_command("set", "passdb/%s" % player, json.dumps(passItem))
