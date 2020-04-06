import logging
import re

from statemachine import StateMachine, State

from HavokMud.account import Account
from HavokMud.commandhandler import CommandHandler
from HavokMud.logging_support import AccountLogMessage
from HavokMud.player import Player
from HavokMud.utils import validate_email, validate_yes_no, validate_password, validate_pc_name, validate_sex

logger = logging.getLogger(__name__)


class LoginStateMachine(StateMachine):
    initial = State("INITIAL", initial=True)
    get_email = State("GET_EMAIL")
    confirm_email = State("CONFIRM_EMAIL")
    get_new_user_password = State("GET_NEW_USER_PASSWORD")
    confirm_password = State("CONFIRM_PASSWORD")
    get_password = State("GET_PASSWORD")
    choose_ansi = State("CHOOSE_ANSI")
    show_motd = State("SHOW_MOTD")
    show_credits = State("SHOW_CREDITS")
    disconnect = State("DISCONNECT")
    show_account_menu = State("SHOW_ACCOUNT_MENU")
    show_player_list = State("SHOW_PLAYER_LIST")
    get_new_password = State("GET_NEW_PASSWORD")
    confirm_new_password = State("CONFIRM_NEW_PASSWORD")
    enter_confirm_code = State("ENTER_CONFIRM_CODE")
    resend_confirm_email = State("RESEND_CONFIRM_EMAIL")
    show_creation_menu = State("SHOW_CREATION_MENU")
    choose_name = State("CHOOSE_NAME")
    choose_sex = State("CHOOSE_SEX")
    choose_race = State("CHOOSE_RACE")
    choose_class = State("CHOOSE_CLASS")
    choose_stats = State("CHOOSE_STATS")
    choose_alignment = State("CHOOSE_ALIGNMENT")
    reroll_abilities = State("REROLL_ABILITIES")
    playing = State("PLAYING")

    go_to_get_email = initial.to(get_email)
    go_to_creation_menu = reroll_abilities.to(show_creation_menu)
    process_input = get_email.to(disconnect, get_email, confirm_email, get_password) | \
                    confirm_email.to(get_email, confirm_email, get_new_user_password) | \
                    get_new_user_password.to(get_new_user_password, confirm_password) | \
                    confirm_password.to(get_new_user_password, choose_ansi) | \
                    get_password.to(disconnect, show_account_menu) | \
                    choose_ansi.to(choose_ansi, resend_confirm_email, show_account_menu) | \
                    show_motd.to(show_account_menu) | \
                    show_credits.to(show_account_menu) | \
                    disconnect.to(disconnect) | \
                    show_account_menu.to(choose_ansi, get_new_password, show_motd, show_credits, show_player_list,
                                         show_creation_menu, playing, enter_confirm_code, resend_confirm_email,
                                         disconnect, show_account_menu) | \
                    show_player_list.to(show_account_menu) | \
                    get_new_password.to(get_new_password, confirm_new_password, show_account_menu) | \
                    enter_confirm_code.to(show_account_menu) | \
                    show_creation_menu.to(show_creation_menu, choose_name, choose_sex, reroll_abilities, choose_race,
                                          choose_class, choose_stats, choose_alignment, show_account_menu) | \
                    choose_name.to(show_creation_menu, choose_name, show_account_menu) | \
                    choose_sex.to(choose_sex, show_creation_menu) | \
                    reroll_abilities.to(show_creation_menu) | \
                    choose_alignment.to(show_creation_menu) | \
                    choose_race.to(show_creation_menu) | \
                    choose_stats.to(show_creation_menu) | \
                    choose_class.to(show_creation_menu) | \
                    playing.to(playing) | \
                    resend_confirm_email.to(show_account_menu)

    def append_output(self, output):
        self.model.append_output(output)

    def append_line(self, output):
        self.model.append_line(output)

    def set_echo(self, value):
        self.model.set_echo(value)

    def do_disconnect(self):
        self.model.disconnect()

    # State actions

    def on_process_input(self):
        func = getattr(self, "on_%s" % self.current_state_value, None)
        if not func or not hasattr(func, "__call__"):
            raise ValueError("No handler for state %s" % self.current_state_value)

        return func()

    def on_initial(self):
        return self.get_email

    def on_get_email(self):
        if not self.model.tokens:
            return self.disconnect

        email = self.model.tokens[0].lower()

        # Validate email
        if not validate_email(email):
            self.append_line("Illegal email address, please try again.")
            return self.get_email

        self.model.account = Account.lookup_by_email(self.model.server, self.model.connection, email)

        # Check if we have banned the source IP/hostname
        if self.model.account.is_sitelocked():
            self.append_line("Sorry, your site is temporarily banned.")
            return self.disconnect

        if self.model.account.email == email:
            # Existing account
            return self.get_password

        if self.model.server.is_wizlocked:
            self.append_line("Sorry, no new accounts at this time, please try again later")
            if self.model.server.wizlock_reason:
                self.append_line(self.model.server.wizlock_reason)
                return self.disconnect

        # New account
        self.model.account.email = email
        return self.confirm_email

    def on_confirm_email(self):
        answer = validate_yes_no(self.model.tokens)
        if answer is None:
            self.append_output("Please type Y or N: ")
            return self.confirm_email

        if answer:
            self.set_echo(True)
            self.append_line("New account.  Welcome!")
            return self.get_new_user_password

        self.append_line("OK, then what IS it then?")
        return self.get_email

    def on_get_new_user_password(self):
        self.set_echo(True)
        password = validate_password(self.model.tokens)
        if not password:
            self.append_line("Illegal password.")
            return self.get_new_user_password

        self.model.account.password = password
        return self.confirm_password

    def on_confirm_password(self):
        self.set_echo(True)
        if not validate_password(self.model.tokens, self.model.account.password):
            self.append_line("Passwords don't match.")
            return self.get_new_user_password

        return self.choose_ansi

    def on_get_password(self):
        self.set_echo(True)
        if not self.model.tokens:
            return self.disconnect

        if not validate_password(self.model.tokens, self.model.account.password):
            self.append_line("Wrong password.")
            logger.warning("Bad password from %s" % self.model.account.email)
            return self.disconnect

        logger.info(AccountLogMessage(self.model.account,
                                      "%s has connected from %s (%s)" %
                                      (self.model.account.email, self.model.account.ip_address,
                                       self.model.account.get_hostname()), _global=True))

        return self.show_account_menu

    def on_choose_ansi(self):
        answer = validate_yes_no(self.model.tokens)
        if answer is None:
            self.append_output("Please type Y or N: ")
            return self.choose_ansi

        self.model.account.ansi_mode = answer
        self.model.connection.ansi_mode = answer

        if answer:
            self.append_line("$c0012A$c0010N$c0011S$c0014I$c0007 colors enabled.\r\n")

        self.model.account.save_to_db()

        if not self.model.account.confcode:
            return self.resend_confirm_email

        return self.show_account_menu

    def on_show_motd(self):
        return self.show_account_menu

    def on_show_credits(self):
        return self.show_account_menu

    def on_disconnect(self):
        # Shouldn't actually get here, but if it does...  disconnect!
        self.append_output(None)
        return self.disconnect

    account_menu_map = {
        '1': choose_ansi,
        '2': get_new_password,
        '3': show_motd,
        '4': show_credits,
        '5': {'condition': 'confirmed', 'state': show_player_list},
        '6': {'condition': 'confirmed', 'state': show_creation_menu},
        '7': {'condition': 'confirmed', 'state': playing},
        'e': {'condition': 'not_confirmed', 'state': enter_confirm_code},
        'r': {'condition': 'not_confirmed', 'state': resend_confirm_email},
        'q': disconnect,
    }

    def on_show_account_menu(self):
        if not self.model.tokens:
            return self.show_account_menu

        choice = self.model.tokens[0].lower()[:1]
        item = self.account_menu_map.get(choice, None)
        if item:
            if not isinstance(item, dict):
                item = {'state': item}
            state = item.get('state', None)
            allowed = True
            condition = item.get('condition', None)
            if condition:
                allowed = False
                if condition == 'confirmed':
                    allowed = self.model.account.confirmed
                elif condition == 'not_confirmed':
                    allowed = not self.model.account.confirmed

            if allowed:
                return state

        self.append_line("Invalid Choice...  Try again.")
        return self.show_account_menu

    def on_show_player_list(self):
        return self.show_account_menu

    def on_get_new_password(self):
        password = validate_password(self.model.tokens)
        if not password:
            self.set_echo(True)
            self.append_line("Illegal password.")
            return self.get_new_password

        self.model.account.new_password = password
        self.set_echo(True)
        return self.confirm_new_password

    def on_confirm_new_password(self):
        if not validate_password(self.model.tokens, self.model.account.new_password):
            self.set_echo(True)
            self.append_line("Passwords don't match.")
            return self.show_account_menu

        self.set_echo(True)
        self.model.account.password = self.model.account.new_password
        self.model.account.new_password = None
        self.model.account.save_to_db()
        self.model.account.update_redis()

        self.append_line("Password changed...")
        return self.show_account_menu

    def on_enter_confirm_code(self):
        if not self.model.tokens:
            self.append_line("Entry aborted.")
            return self.show_account_menu

        confcode = self.model.tokens[0].lower()
        if self.model.account.confcode.lower() == confcode:
            self.model.account.confirmed = True
            self.model.account.confcode = None
            self.model.account.save_to_db()
            self.append_line("\r\nYour email is now confirmed, you can now play.  Thank you!")
        else:
            self.model.account.confirmed = False
            self.model.account.save_to_db()
            self.append_line("\r\nConfirmation code does not match our records.  Please try again,")
            self.append_line("or resend the confirmation email to get a new code.\r\n")

        return self.show_account_menu

    def on_resend_confirm_email(self):
        return self.show_account_menu

    creation_menu_map = {
        '1': choose_name,
        '2': choose_sex,
        '3': choose_race,
        '4': choose_class,
        '5': {'handler': 'handle_choose_stats'},
        'd': {'handler': 'handle_done'},
        'r': reroll_abilities,
    }

    def on_show_creation_menu(self):
        if not self.model.tokens:
            return self.show_creation_menu

        choice = self.model.tokens[0].lower()[:1]
        item = self.creation_menu_map.get(choice, None)
        if item:
            if not isinstance(item, dict):
                item = {'state': item}
            state = item.get('state', None)
            handler = item.get('handler', None)
            if handler:
                func = getattr(self, handler, None)
                if func and hasattr(func, '__call__'):
                    return func()
            else:
                return state

        self.append_line("Invalid Choice...  Try again.")
        return self.show_creation_menu

    def handle_choose_stats(self):
        self.model.account.player.rerolls = 20
        if self.model.account.player.klass:
            return self.choose_stats

        self.append_line("\r\nPlease select a class first.")
        return self.show_creation_menu

    def handle_done(self):
        if self.model.account.player.name is None:
            self.append_line("Please enter a valid player name.")
            return self.show_creation_menu

        if self.model.account.player.sex is None:
            self.append_line("Please enter a proper sex.")
            return self.show_creation_menu

        if self.model.account.alignment is None:
            self.append_line("Please choose an alignment.")
            return self.show_creation_menu

        if not self.model.account.stats:
            self.append_line("Please pick your stats.")
            return self.show_creation_menu

        logger.info("%s [%s] new player" % (self.model.account.player.name, self.model.account.get_hostname()))
        self.model.account.player.complete = True
        self.model.account.player.save_to_db()
        return self.show_account_menu

    def on_choose_name(self):
        if not self.model.tokens:
            self.append_line("Never mind then.")
            return self.show_creation_menu

        name = self.model.tokens[0]
        player = Player.lookup_by_name(self.model.account, name)
        if player.name == name:
            if player.account != self.model.account:
                self.append_line("Name is already taken.")
                return self.choose_name
            elif player.complete:
                self.append_line("That PC is completed already.")
                return self.show_account_menu

            # Incomplete PC
            self.model.account.player = player
            return self.show_creation_menu

        if not validate_pc_name(name):
            self.append_line("That name is not acceptable and has been blacklisted")
            return self.show_creation_menu

        if not self.model.account.player.name:
            self.model.account.player = Player(self.model.server, self.model.connection, self.model.account)
            self.model.account.player.roll_abilities()

        self.model.account.player.display_name = name
        self.model.account.player.name = name.lower()
        self.model.account.player.save_to_db()
        self.model.account.players.append(name.lower())
        self.model.account.save_to_db()
        self.model.account.update_redis()
        return self.show_creation_menu

    def on_choose_sex(self):
        answer = validate_sex(self.model.tokens)
        if not answer:
            self.append_line("That's not a valid sex...")
            return self.choose_sex

        self.model.account.player.sex = answer.upper()
        return self.show_creation_menu

    def on_choose_race(self):
        # TODO:  do this!
        self.model.account.player.race = "elf"
        return self.show_creation_menu

    def on_choose_class(self):
        # TODO:  do this!
        self.model.account.player.klass = "warrior"
        return self.show_creation_menu

    def on_choose_stats(self):
        choices = []
        for token in self.tokens:
            pattern = re.compile(r'^%s.*' % token, re.I)
            roots = list(filter(None, map(lambda x: pattern.findall(x), Player.stats_list)))
            roots = [item for item_list in roots for item in item_list]
            choice = None
            if len(roots) > 1:
                self.append_line("Choice %s too vague:  could be any of %s" % (token, roots))
            elif len(roots) == 1:
                choice = roots[0]
            choices.append(choice)

        if len([choice for choice in choices if choice is None]) != 0:
            self.append_line("These choices are not valid.  Please try again.")
        else:
            self.model.account.player.stats["choices"] = choices
            self.model.account.player.finalize_abilities()

        return self.show_creation_menu

    def on_choose_alignment(self):
        # TODO: do this
        self.model.account.player.alignment = 0
        return self.show_creation_menu

    def on_reroll_abilities(self):
        # Shouldn't get here?
        return self.show_creation_menu

    def on_playing(self):
        # Shouldn't get here!
        return self.playing

    # On entry to states
    def on_enter_initial(self):
        pass

    def on_enter_get_email(self):
        self.append_output("What is your account name (email address)? ")

    def on_enter_confirm_email(self):
        self.append_output("Did I get that right, %s (Y/N)? " % self.model.account.email)

    def on_enter_get_new_user_password(self):
        self.append_output("Give me a password for %s: " % self.model.account.email)
        self.set_echo(False)

    def on_enter_confirm_password(self):
        self.append_output("Please retype password: ")
        self.set_echo(False)

    def on_enter_get_password(self):
        self.append_output("Password: ")
        self.set_echo(False)

    def on_enter_choose_ansi(self):
        self.append_output("Would you like ANSI colors? (Y/N) ")

    def on_enter_show_motd(self):
        motd = "MOTD will be eventually read from the database\r\n\r\n"
        self.append_output(motd)
        self.append_line("\r\n[PRESS RETURN]")

    def on_enter_show_credits(self):
        credits = "Credits will be eventually read from the database\r\n\r\n"
        self.append_output(credits)
        self.append_line("\r\n[PRESS RETURN]")

    def on_enter_disconnect(self):
        self.append_line("Goodbye.")
        self.do_disconnect()

    def on_enter_show_account_menu(self):
        self.append_output(
            {"template": "account_menu.jinja", "params": {"server": self.model.server, "account": self.model.account}})

    def on_enter_show_player_list(self):
        self.append_output({"template": "account_player_list.jinja",
                            "params": {"server": self.model.server, "account": self.model.account}})

    def on_enter_get_new_password(self):
        self.append_output("Please enter new password: ")
        self.set_echo(False)

    def on_enter_confirm_new_password(self):
        self.on_enter_confirm_password()

    def on_enter_enter_confirm_code(self):
        self.append_output("Please enter the confirmation code you were emailed: ")

    def on_enter_resend_confirm_email(self):
        if self.model.account.confcode:
            self.append_line("Resending your confirmation email...")
        else:
            self.append_line("Sending your confirmation email...")
        self.model.account.send_confirmation_email()
        self.append_line("Hit enter to continue")

    def on_enter_show_creation_menu(self):
        self.model.account.player = Player(self.model.server, self.model.connection, self.model.account)
        self.append_output({"template": "creation_menu.jinja",
                            "params": {"server": self.model.server, "player": self.model.account.player}})

    def on_enter_choose_name(self):
        self.append_output("Choose the name of your new PC: ")

    def on_enter_choose_sex(self):
        self.append_output("What is your sex (M)ale/(F)emale/(N)eutral)? ")

    def on_enter_choose_race(self):
        self.append_output("For help type '?'- will list level limits.\r\n RACE: ")
        self.model.account.player.klass = None

    def on_enter_choose_class(self):
        self.append_output("\r\nSelect your class now.\r\nEnter ? for help.\r\n CLASS: ")
        self.model.account.player.alignment = None
        self.model.account.player.stats.clear()

    def on_enter_choose_stats(self):
        self.append_line("\r\nSelect your stat priority, by listing them from highest to lowest")
        self.append_line("separated by spaces... don't repeat any stat")
        self.append_line("For example: 'S I W D Co Ch' would put the highest roll in Strength,")
        self.append_line("next in Intelligence, Wisdom, Dexterity, Constitution and lastly")
        self.append_output("Charisma.\r\nYour choices? ")

    def on_enter_choose_alignment(self):
        self.append_line("Your alignment is an indication of how well or poorly your moral conduct")
        self.append_line("in the game has fared.  It is represented numerically in a range from -1000")
        self.append_line("($c000RChaotic Evil$c000w) to 1000 ($c000WLawful Good$c000w), with 0 being")
        self.append_line("neutral.  Generally, if you kill \"Good\" mobs, you will gravitate towards evil")
        self.append_line("and vice-versa.  Some spells and skills will also affect your alignment when used.")
        self.append_line("For example, 'backstab' makes you more evil, and the 'heal' spell makes you more good.")
        self.append_output("Please select your starting alignment ($c000WGood$c000w/Neutral/$c000REvil$c000w): ")

    def on_enter_reroll_abilities(self):
        self.model.account.player.reroll_abilities()
        self.model.account.player.save_to_db()
        self.go_to_creation_menu()

    def on_enter_playing(self):
        # TODO: ask which player and launch that one
        self.model.account.current_player = Player.lookup_by_name(self.model.account.players[0])
        self.model.player = self.model.account.current_player
        self.model.connection.handler = CommandHandler(self.model.server, self.model.connection)
