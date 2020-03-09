import logging
import socket
import stackless
import traceback
import weakref
from threading import Lock

from HavokMud.connection import Connection
from HavokMud.database import Databases
from HavokMud.dnslookup import DNSLookup


class Server:
    def __init__(self, host, port, isLocal=False):
        self.host = host
        self.port = port

        self.user_lock = Lock()
        self.user_index = weakref.WeakValueDictionary()
        self.wizlocked = False
        self.wizlock_reason = None
        self.dbs = Databases(isLocal)
        self.dns_lookup = DNSLookup()

        stackless.tasklet(self.run)()

    def run(self):
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind((self.host, self.port))
        listen_socket.listen(5)

        logging.info("Accepting connections on %s %s", self.host, self.port)
        try:
            while True:
                (clientSocket, clientAddress) = listen_socket.accept()
                Connection(self, clientSocket, clientAddress)
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
