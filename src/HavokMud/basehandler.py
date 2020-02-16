import sys
from threading import Lock


class BaseHandler(object):
    def __init__(self, server, connection):
        self.server = server
        self.connection = connection
        self.output = []
        self.output_lock = Lock()

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
