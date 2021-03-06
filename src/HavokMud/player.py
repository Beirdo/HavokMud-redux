from HavokMud.database_object import DatabaseObject
from HavokMud.utils import roll_dice
from HavokMud.wallet import WalletType, Wallet


class Player(DatabaseObject):
    __fixed_fields__ = ["server", "connection", "account", "wallets"]
    __database__ = None

    def __init__(self, connection=None, account=None, other=None):
        DatabaseObject.__init__(self)
        self.__real_class__ = self.__class__

        if other:
            self.__dict__.update(other.__dict__)
        else:
            self.__database__ = self.server.dbs.user_db
            self.connection = connection
            self.account = account
            self.email = account.email
            self.rolls = [0, 0, 0, 0, 0, 0]
            self.rerolls = None
            self.name = None
            self.display_name = None
            self.sex = None
            self.race = None
            self.klass = None
            self.stats = {}
            self.alignment = None
            self.complete = False
            self.wallets = {}
            self.wallet_password = {}
            self.wallet_owner_key = {}
            self.wallet_active_key = {}
            self.wallet_keys = {}

    def set_connection(self, connection):
        if self.connection:
            self.connection.disconnect()
            connection.handler = self.connection.handler
        self.account.connection = connection
        self.connection = connection

    @staticmethod
    def lookup_by_name(account, name):
        player = Player(account.connection, account)

        # if not in dynamo: return with empty name field
        player.load_from_db(email=player.email, name=name)

        if not player.name:
            return player

        player.wallets = {
            WalletType.Carried: Wallet.load(player, WalletType.Carried),
            WalletType.Stored: Wallet.load(player, WalletType.Stored),
        }

        return player

    def create_wallets(self):
        self.wallets = {
            WalletType.Carried: Wallet.load(self, WalletType.Carried),
            WalletType.Stored: Wallet.load(self, WalletType.Stored),
        }
        self.save_to_db()

    def append_line(self, output):
        if output is None:
            self.append_output(None)
        else:
            self.append_output(output + "\r\n")

    def append_output(self, output):
        self.connection.output_channel.send(output)

    def roll_abilities(self):
        if self.rerolls <= 0:
            self.rerolls = 0
            self.append_line("Sorry, you are out of rerolls.")
            return

        self.rerolls -= 1
        self.append_line("Rolling abilities.  %s rerolls left." % self.rerolls)

        self.rolls = [self.ability_roll(output=True) for i in range(len(self.stats_list))]
        self.save_to_db()

    def _ability_roll(self, output=False):
        roll = roll_dice("4d6k3")
        details = roll.get('details', [{}]).pop(0)
        if output:
            self.append_line(details.get("text"))
        return roll.get("total", 0)

    stats_list = ["strength", "intelligence", "wisdom", "dexterity", "constitution", "charisma"]

    def finalize_abilities(self):
        choices = self.stats.get("choices", [])
        base = {stat: self.rolls[index] for (index, stat) in enumerate(choices)}
        self.stats["base"] = base
        self.stats["race"] = self.race.stats_modifier
        self.stats.update({klass.name: klass.stats_modifier for klass in self._klasses})
        self.stats["effective"] = {stat: sum([item.get(stat) for item in self.stats]) for stat in self.stats_list}

        max_hp = sum([klass.base_hp for klass in self._klasses])
        self.hit_points["base"] = max_hp
        self.hit_points["race"] = self.race.hp_modifier
        self.hit_points["effective"] = sum(self.hit_points.values())

        delattr(self, "rolls")
        self.save_to_db()
