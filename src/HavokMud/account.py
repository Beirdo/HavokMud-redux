import uuid
from threading import Lock

from HavokMud.database import account_db
from HavokMud.database_object import DatabaseObject


class Account(DatabaseObject):
    __fixed_fields__ = ["server", "connection", "hostname_lock", "player", "current_player"]
    __database__ = account_db

    def __init__(self, server, connection, email=None):
        self.server = server
        self.connection = connection
        self.hostname_lock = Lock()
        self.player = None
        self.current_player = None

        self.email = email
        self.password = None  # SHA512 digest
        self.new_password = None    # SHA512 digest
        self.hostname = None  # TODO: add this from connection info
        self.ansi_mode = False
        self.confcode = None
        self.confirmed = False
        self.players = []

    @staticmethod
    def lookup_by_email(server, connection, email):
        # Look this up in DynamoDB
        account = Account(server, connection, email)

        connection.ansi_mode = account.ansi_mode

        # if not in dynamo: will return with empty email field
        account.load_from_db(email=email)
        return account

    def send_confirmation_email(self):
        if not self.confcode:
            self.confcode = str(uuid.uuid4())
            self.save_to_db()

        # send an email with the confcode in it

    def is_sitelocked(self):
        # TODO
        # look up the connection's IP and hostname for possible bans
        return False

    def get_hostname(self):
        with self.hostname_lock:
            return self.hostname
