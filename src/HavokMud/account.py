import uuid
from threading import Lock


class Account(object):
    def __init__(self, server, connection, email=None):
        self.server = server
        self.connection = connection
        self.email = email
        self.password = None  # SHA512 digest
        self.new_password = None    # SHA512 digest
        self.hostname = None  # TODO: add this from connection info
        self.hostname_lock = Lock()
        self.ansi_mode = False
        self.confcode = None
        self.confirmed = False
        self.player = None
        self.current_player = None
        self.players = []

    @staticmethod
    def lookup_by_email(server, connection, email):
        # Look this up in DynamoDB
        account = Account(server, connection, email)

        connection.ansi_mode = account.ansi_mode

        # if not in dynamo: return with empty email field
        return account

    def send_confirmation_email(self):
        if not self.confcode:
            self.confcode = str(uuid.uuid4())
        # send an email with the confcode in it

    def is_sitelocked(self):
        # TODO
        # look up the connection's IP and hostname for possible bans
        return False

    def get_hostname(self):
        with self.hostname_lock:
            return self.hostname

    def save(self):
        # TODO: save to dynamoDB
        pass
