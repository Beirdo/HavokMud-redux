class Player(object):
    def __init__(self, server, connection, account):
        self.server = server
        self.connection = connection
        self.account = account
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

        # Look this up in DynamoDB
        player.name = "Test"

        # if not in dynamo: return with empty email field
        return player

    def reroll_abilities(self):
        # TODO
        pass

    def roll_abilities(self):
        # TODO
        pass

    def save(self):
        # TODO
        pass