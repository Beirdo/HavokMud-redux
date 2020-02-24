import logging
import stackless
import time

from HavokMud.ansicolors import AnsiColors
from HavokMud.jinjaprocessor import jinja_processor
from HavokMud.loginhandler import LoginHandler
from HavokMud.user import User

logger = logging.getLogger(__name__)


class Connection:
    telnet_cmd_with_options = range(251, 255)  # 251-254.  Remember end param is end + 1

    def __init__(self, server, client_socket, client_address):
        self.server = server
        self.client_socket = client_socket
        self.client_address = client_address
        self.disconnected = False

        self.output_channel = stackless.channel()
        self.input_channel = stackless.channel()
        self.jinja_in_channel = jinja_processor.in_channel
        self.jinja_out_channel = stackless.channel()
        self.handler = None
        self.read_buffer = ""
        self.ansi_mode = True
        self.ansi = AnsiColors()

        self.user = User(self)
        self.user_id = id(self.user)

        logging.info("Connected %d from %s", self.user_id, self.client_address)

        self.set_handler(LoginHandler(self.server, self))

        stackless.tasklet(self.read_tasklet)()
        stackless.tasklet(self.write_tasklet)()

    def disconnect(self):
        self.user = None
        if self.disconnected:
            raise RuntimeError("Unexpected call")
        self.disconnected = True
        self.client_socket.close()

    def set_echo(self, value):
        if not value:
            # IAC, WILL, TELOPT_ECHO
            self.write_raw(b'\xff\xfb\x01')
        else:
            # IAC, WONT, TELOPT_ECHO
            self.write_raw(b'\xff\xfc\x01')

    def write_raw(self, s):
        self.write(s, False)

    def write(self, s, string_mode=True):
        if string_mode:
            s = self.ansi.convert_string(s, self.ansi_mode)
            s = s.encode("ascii")
        self.client_socket.send(s)

    def write_line(self, s):
        self.write(s + "\r\n")

    def read_line(self, string_mode=True):
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

            try:
                v = self.client_socket.recv(1000)
            except Exception:
                v = b""

            # An empty string indicates disconnection.
            if not v:
                return None

            # Deal with any embedded telnet commands before decoding UTF-8
            print(v)
            v = self.handle_telnet_commands(v)

            if not v:
                # This was all telnet commands, just eat it.
                continue

            if string_mode:
                v = v.decode("utf-8", "replace")

            s += v

    def handle_telnet_commands(self, input):
        # Commands defined in RFC854
        # Options defined in RFC855
        # 0xFF 0xF0      is "IAC SE" - end of subnegotiation
        # 0xFF 0xF1      is "IAC NOP"
        # 0xFF 0xF2      is "IAC DataMark" - should have TCP urgent
        # 0xFF 0xF3      is "IAC BRK" - break
        # 0xFF 0xF4      is "IAC IP" - interrupt process
        # 0xFF 0xF5      is "IAC AO" - abort output
        # 0xFF 0xF6      is "IAC AYT" - are you there
        # 0xFF 0xF7      is "IAC EC" - erase character
        # 0xFF 0xF8      is "IAC EL" - erase line
        # 0xFF 0xF9      is "IAC GA" - go ahead
        # 0xFF 0xFA      is "IAC SB" - start subnegotiation
        # 0xFF 0xFB 0xXX is "IAC WILL option"
        # 0xFF 0xFC 0xXX is "IAC WONT option"
        # 0xFF 0xFD 0xXX is "IAC DO option"
        # 0xFF 0xFE 0xXX is "IAC DONT option"
        # 0xFF 0xFF      is "IAC IAC" - send 0xFF

        start = 0
        while b'\xff' in input:
            index = input.find(b'\xff', start)
            if index == -1:
                break
            length = 2
            command = input[index + 1]
            if command == b'\xff':
                # Leave one 0xFF, and continue searching.
                end = index + 1
                start = index + 1
            else:
                option = None
                if command in self.telnet_cmd_with_options:
                    option = input[index + 2]
                    length += 1
                end = index + length
                # At this time, I don't want to do anything with these commands, just strip them out.
                # print("Telnet command: %s %s" % (command, option))

            input = input[:index] + input[end:]

        return input

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

            if isinstance(data, str):
                self.write(data)
            elif isinstance(data, dict):
                data["channel"] = self.jinja_out_channel
                self.jinja_in_channel.send(data)
                data = self.jinja_out_channel.receive()
                self.write(data)

    def read_tasklet(self):
        while not self.disconnected:
            line = self.read_line()
            self.input_channel.send(line)
