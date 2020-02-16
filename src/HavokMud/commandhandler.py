from HavokMud.basehandler import BaseHandler


class CommandHandler(BaseHandler):
    commands = {
        "look": "CommandHandler.handler_standard",
        "say": "CommandHandler.handler_standard",
        "quit": "CommandHandler.handler_standard",
        "help": "CommandHandler.handler_standard",
    }

    def send_prompt(self, prompt):
        self.append_output(prompt)

    def handle_input(self, tokens):
        verb = tokens[0]
        if not verb:
            return

        handler = self.commands.get(verb, None)
        if handler is None:
            self.append_line("Unknown command.  Type 'help' to see a list of available commands.")
        else:
            (klass, funcname) = handler.split(".")
            if klass == self.__class__.__name__:
                instance = self
            else:
                klass = locals().get(klass, None)
                if klass is None:
                    instance = None
                else:
                    instance = klass(self.connection)

            if instance is None:
                func = None
            else:
                if funcname == "handler_standard":
                    funcname = "command_%s" % verb

                if not hasattr(instance, funcname):
                    func = None
                else:
                    func = getattr(instance, funcname)
                    # print(handler, func)
                    if not hasattr(func, "__call__"):
                        func = None

            if func is None:
                self.append_line("Handler %s not valid in class %s" % (handler, self.__class__.__name__))
            else:
                func(tokens)

    def command_look(self, tokens):
        user_list = self.server.list_users()
        self.append_line("There are %d users connected:" % len(user_list))
        self.append_line("%-16s %-15s %s" % ("Name", "Host", "Port"))
        self.append_line("-" * 40)
        for user in user_list:
            (host, port) = user.connection.client_address
            self.append_line("%-16s %-15s %s" % ("Unknown", host, port))

    def command_say(self, tokens):
        line = " ".join(tokens[1:])
        second_party_prefix = "Someone says: "
        for user in self.server.list_users():
            if user is self.connection.user:
                prefix = "You say: "
            else:
                prefix = second_party_prefix
            user.connection.handler.append_line(prefix + "\"%s\"" % line)

    def command_quit(self, tokens):
        self.append_output(None)

    def command_help(self, tokens):
        self.append_line("Commands:")
        for verb in self.commands.keys():
            self.append_line("  " + verb)
