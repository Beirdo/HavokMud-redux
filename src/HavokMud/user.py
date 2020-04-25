import logging
import stackless
import time
import traceback

from HavokMud.account import Account
from HavokMud.logging_support import AccountLogHandler, PlayerLogHandler, AccountLogMessage

logger = logging.getLogger(__name__)

class RemoteDisconnectionError(RuntimeError):
    pass


class User(object):
    def __init__(self, connection):
        self.connection = connection
        self.server = self.connection.server
        self.account = Account(self.server, self.connection, None)
        self.disconnect = False

        self.server.register_user(self)

        # The tasklet will hold a reference to the user keeping the instance
        # alive as long as it is handling commands.
        stackless.tasklet(self.run)()

    def __del__(self):
        self.server.unregister_user(self)

    def run(self):
        try:
            while not self.disconnect:
                self.handle_command()

            self.on_user_disconnection()
        except RemoteDisconnectionError:
            self.on_remote_disconnection()
            self.connection.user = None
            self.connection = None
        except Exception:
            traceback.print_exc()
        finally:
            if self.connection:
                if self.account.email:
                    AccountLogHandler().closeEmail(self.account.email)
                if self.account.player:
                    PlayerLogHandler().closePlayer(self.account.player.name)
                self.connection.disconnect()
                self.connection = None

    def handle_command(self):
        handler = self.connection.handler
        if handler is None:
            time.sleep(0.5)
            return

        if handler.external:
            handler.launch_external_command()
            handler.handler_callback()
            if handler.editor_callback:
                handler.editor_callback()
            self.connection.set_handler(handler.old_handler)
        else:
            handler.send_prompt("> ")

            line = self.connection.input_channel.receive()
            if line is None:
                raise RemoteDisconnectionError()

            tokens = handler.tokenize_input(line)
            handler.handle_input(tokens)

    def on_remote_disconnection(self):
        logger.info(AccountLogMessage(self.account, "Disconnected %s (remote)" % self.account.ip_address, _global=True))

    def on_user_disconnection(self):
        logger.info(AccountLogMessage(self.account, "Disconnected %s (local)" % self.account.ip_address, _global=True))
