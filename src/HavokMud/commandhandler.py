import re

from HavokMud.basehandler import BaseHandler


class CommandHandler(BaseHandler):
    commands = {
        "look": "CommandHandler.handler_standard",
        "say": "CommandHandler.handler_standard",
        "quit": "CommandHandler.handler_standard",
        "help": {
            "handler": "CommandHandler.handler_standard",
            "help": "Use HELP COMMAND_NAME to get help on a specific command\r\nUse HELP to get a list of commands",
        },
        "north": "CommandHandler.handler_standard",
        "n": {"root": "north"},
        "list": {
            "handler": "CommandHandler.handler_standard",
            "help": "Use LIST USERS to list online users\r\nUse LIST COMMANDS to list commands",
        },
        "welcome": "CommandHandler.handler_standard",
        "echo": "CommandHandler.handler_standard",
    }

    def __init__(self, server, connection):
        BaseHandler.__init__(self, server, connection)
        self.commands.update({key: {"handler": value} for (key, value) in self.commands.items()
                              if not isinstance(value, dict)})

    def send_prompt(self, prompt):
        self.append_output(prompt)

    def defangle_verb(self, verb):
        while True:
            verb = verb.lower()
            handler_info = self.commands.get(verb, None)
            if not isinstance(handler_info, dict):
                handler_info = {"handler": handler_info}

            root = handler_info.get("root", None)
            if root:
                verb = root
                continue

            handler = handler_info.get("handler", None)
            if handler:
                return (verb, handler_info)

            pattern = re.compile(r'^%s.*' % verb, re.I)
            roots = list(filter(None, map(lambda x: pattern.findall(x), self.commands.keys())))
            roots = [item for item_list in roots for item in item_list]
            if not roots:
                return

            if len(roots) > 1:
                self.append_line("Command too vague:  could be any of %s" % roots)
                return

            verb = roots[0]

    def handle_input(self, tokens):
        verb = tokens[0]
        if not verb:
            return

        result = self.defangle_verb(verb)
        if not result:
            self.append_line("Unknown command.  Type 'help' to see a list of available commands.")
            return

        (verb, handler_info) = result
        handler = handler_info.get("handler", None)
        if not handler:
            return

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
            user.connection.handler.append_line(prefix + "\"%s$c0007\"" % line)

    def command_quit(self, tokens):
        self.append_output(None)

    def command_help(self, tokens):
        if len(tokens) > 1:
            verb = tokens[1]
            result = self.defangle_verb(verb)
            if not result:
                self.append_line("I can't give help on a command I don't understand")
                return

            (verb, handler_info) = result
            help_text = handler_info.get("help", None)
            if not help_text:
                self.append_line("There is no available help for command: %s" % verb)
                return

            self.append_line("Help for command: %s" % verb)
            self.append_line(help_text)
        else:
            self.append_line("Commands:")
            for (verb, handler_info) in sorted(self.commands.items()):
                if "root" not in handler_info:
                    subs = dict(filter(lambda x: x[1].get("root", None) == verb, list(self.commands.items())))
                    if subs:
                        postamble = " (" + ", ".join(sorted(subs.keys())) + ")"
                    else:
                        postamble = ""

                    self.append_line("  " + verb + postamble)

    def command_north(self, tokens):
        self.append_line("You move north")

    def command_list(self, tokens):
        if len(tokens) < 2:
            self.command_help(["help", "list"])
            return

        verb = tokens[1].lower()
        if verb == "users":
            self.command_look(["look"])
        elif verb == "commands":
            self.command_help(["help"])
        else:
            self.append_line("Whatcha talkin' about, Willis?")

    def command_welcome(self, tokens):
        self.append_output({"template": "welcome_page.jinja", "params": {"tokens": tokens}})

    def command_echo(self, tokens):
        if len(tokens) < 2:
            echo = not self.echo
        else:
            token = tokens[1].lower()
            echo = (token == "on")
        self.set_echo(echo)
