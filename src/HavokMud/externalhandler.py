import logging
import stackless
import subprocess

from HavokMud.basehandler import BaseHandler

logger = logging.getLogger(__name__)


class ExternalHandler(BaseHandler):
    external = True

    def __init__(self, server, connection, command: list):
        BaseHandler.__init__(self, server, connection)
        self.command = command
        self.old_handler = connection.handler
        self.sock_fd = connection.client_socket
        self.proc = None

    def send_prompt(self, prompt):
        pass

    def handle_input(self, tokens):
        pass

    def launch_external_command(self):
        # turn off echo
        self.sock_fd.send(b'\xff\xfb\x01')
        # turn on linemode negotiation
        self.sock_fd.send(b'\xff\xfd\x22')
        # tell the client to go into non-edit mode (character mode)
        self.sock_fd.send(b'\xff\xfa\x22\x01\x00\xff\xf0')

        self.proc = subprocess.Popen(self.command, stdin=self.sock_fd, stdout=self.sock_fd)
        stackless.tasklet(self.communicate)()

    def communicate(self):
        self.proc.communicate()
        # Turn back on echo
        self.sock_fd.send(b'\xff\xfc\x01')
        # Tell the client to go back into edit mode (line mode) and to echo literally
        self.sock_fd.send(b'\xff\xfa\x22\x01\x11\xff\xf0')
