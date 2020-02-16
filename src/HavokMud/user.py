import logging
import stackless
import traceback


class RemoteDisconnectionError(RuntimeError):
    pass


class User:
    def __init__(self, connection):
        self.connection = connection
        self.server = self.connection.server
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
                self.connection.disconnect()
                self.connection = None

    def handle_command(self):
        handler = self.connection.handler
        if handler is None:
            raise RuntimeError("No handler installed!")

        handler.send_prompt("> ")

        line = self.connection.input_channel.receive()
        if line is None:
            raise RemoteDisconnectionError()

        tokens = handler.tokenize_input(line)
        handler.handle_input(tokens)

    def on_remote_disconnection(self):
        logging.info("Disconnected %d (remote)", id(self))

    def on_user_disconnection(self):
        logging.info("Disconnected %d (local)", id(self))

