import logging
import sys
from threading import Lock

logger = logging.getLogger(__name__)


class BaseHandler(object):
    external = False

    def __init__(self, server, connection):
        self.server = server
        self.connection = connection
        self.output = []
        self.output_lock = Lock()
        self.echo = True
        self.account = connection.user.account

    def send_prompt(self, prompt):
        raise RuntimeError("Function %s not implemented in class %s" %
                           (sys._getframe().f_code.co_name, self.__class__.__name__))

    def tokenize_input(self, line):
        tokens = [word.strip() for word in line.strip().split(" ")]
        return tokens

    def handle_input(self, tokens):
        raise RuntimeError("Function %s not implemented in class %s" %
                           (sys._getframe().f_code.co_name, self.__class__.__name__))

    def append_line(self, output):
        if output is None:
            self.append_output(None)
        else:
            self.append_output(output + "\r\n")

    def append_output(self, output):
        self.connection.output_channel.send(output)

    def set_echo(self, value):
        old_echo = self.echo
        self.echo = value
        self.connection.set_echo(value)
        if not old_echo and value:
            self.append_line("")

    def disconnect(self):
        self.append_output(None)
