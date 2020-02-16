import logging
import stackless
import time

from HavokMud.commandhandler import CommandHandler
from HavokMud.user import User


class Connection:
    def __init__(self, server, client_socket, client_address):
        self.server = server
        self.client_socket = client_socket
        self.client_address = client_address
        self.disconnected = False

        self.output_channel = stackless.channel()
        self.input_channel = stackless.channel()
        self.handler = None
        self.read_buffer = ""
        self.string_mode = True

        self.user = User(self)
        self.user_id = id(self.user)

        logging.info("Connected %d from %s", self.user_id, self.client_address)

        self.set_handler(CommandHandler(self.server, self))

        stackless.tasklet(self.read_tasklet)()
        stackless.tasklet(self.write_tasklet)()

    def disconnect(self):
        self.user = None
        if self.disconnected:
            raise RuntimeError("Unexpected call")
        self.disconnected = True
        self.client_socket.close()

    def write(self, s):
        if self.string_mode:
            s = s.encode("utf-8")
        self.client_socket.send(s)

    def write_line(self, s):
        self.write(s + "\r\n")

    def read_line(self):
        start_time = time.time()
        s = self.read_buffer
        while True:
            # If there is a CRLF in the text we have, we have a full
            # line to return to the caller.
            if s.find('\r\n') > -1:
                i = s.index('\r\n')
                # Strip the CR LF.
                line = s[:i]
                self.read_buffer = s[i + 2:]
                while '\x08' in line:
                    i = line.index('\x08')
                    if i == 0:
                        line = line[1:]
                    else:
                        line = line[:i - 1] + line[i + 1:]
                return line

            v = self.client_socket.recv(1000)
            if self.string_mode:
                v = v.decode("utf-8")

            # An empty string indicates disconnection.
            if v == "":
                return None

            s += v

    def set_handler(self, handler):
        self.handler = handler

    def set_string_mode(self, value):
        self.string_mode = value

    def write_tasklet(self):
        while not self.disconnected and not self.user.disconnect:
            data = self.output_channel.receive()
            if data is None:
                self.user.disconnect = True
                continue
            self.write(data)

    def read_tasklet(self):
        while not self.disconnected:
            line = self.read_line()
            self.input_channel.send(line)
