from HavokMud.database_object import DatabaseObject


class Player(DatabaseObject):
    __fixed_fields__ = ["server", "connection", "account"]
    __database__ = None

    def __init__(self, server, connection, account):
        DatabaseObject.__init__(self)
        self.server = server
        self.__database__ = self.server.dbs.user_db
        self.connection = connection
        self.account = account
        self.email = account.email
        self.rolls = [0, 0, 0, 0, 0, 0]
        self.rerolls = None
        self.name = None
        self.sex = None
        self.race = None
        self.klass = None
        self.stats = {}
        self.alignment = None
        self.complete = False

    def set_connection(self, connection):
        if self.connection:
            self.connection.disconnect()
            connection.handler = self.connection.handler
        self.account.connection = connection
        self.connection = connection

    @staticmethod
    def lookup_by_name(account, name):
        player = Player(account.server, account.connection, account)

        # if not in dynamo: return with empty email field
        player.load_from_db(email=player.email, name=name)

        return player

    def reroll_abilities(self):
        # TODO
        pass

    def roll_abilities(self):
        # TODO
        pass
