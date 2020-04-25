#! /usr/bin/env python
import HavokMud.stacklesssocket

# Monkeypatch in the 'stacklesssocket' module, so we get blocking sockets
# which are Stackless compatible.
HavokMud.stacklesssocket.install()

from HavokMud.logging_support import logging_setup
import logging
import socket
import stackless
import traceback
import subprocess

logger = logging.getLogger(__name__)

logging_setup(logging.INFO, True)


class DoEditor(object):
    def __init__(self, sock_fd, addr):
        self.sock_fd = sock_fd
        self.addr = addr
        # turn off echo
        self.sock_fd.send(b'\xff\xfb\x01')
        # turn on linemode negotiation
        self.sock_fd.send(b'\xff\xfd\x22')
        # tell the client to go into non-edit mode (character mode)
        self.sock_fd.send(b'\xff\xfa\x22\x01\x00\xff\xf0')

        #command = ["nano", "-R", "/tmp/shitface"]
        command = ["vim", "-Z", "/tmp/shitface"]
        self.proc = subprocess.Popen(command, stdin=self.sock_fd, stdout=self.sock_fd)
        stackless.tasklet(self.communicate)()

    def communicate(self):
        self.proc.communicate()
        # Turn back on echo
        self.sock_fd.send(b'\xff\xfc\x01')
        # Tell the client to go back into edit mode (line mode) and to echo literally
        self.sock_fd.send(b'\xff\xfa\x22\x01\x11\xff\xf0')


def run():
    listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_socket.bind(("0.0.0.0", 7890))
    logger.info("Listening on %s" % listen_socket.fileno())
    listen_socket.listen(10)

    logger.info("Accepting connections on %s:%s", "0.0.0.0", 7890)
    try:
        while True:
            try:
                (clientSocket, clientAddress) = listen_socket.accept()
                logger.info("Accepting on %s" % clientSocket.fileno())
                DoEditor(clientSocket, clientAddress)
            except Exception as e:
                logger.exception("Exception in accept loop")
                pass
            stackless.schedule()
    except socket.error:
        traceback.print_exc()


stackless.tasklet(run)()
stackless.run()
