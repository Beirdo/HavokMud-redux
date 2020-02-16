import logging
import socket
import stackless
import traceback
import weakref
from threading import Lock

from HavokMud.connection import Connection


class Server:
    def __init__(self, host, port):
        self.host = host
        self.port = port

        self.user_lock = Lock()
        self.user_index = weakref.WeakValueDictionary()

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
