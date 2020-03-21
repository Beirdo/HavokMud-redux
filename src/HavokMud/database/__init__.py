from .account_db import AccountDB
from .handler import DatabaseHandler
from .user_db import UserDB


class Databases(object):
    isLocal = False
    endpoint = None
    use_ssl = True

    def __init__(self, isLocal=False):
        self.handler = DatabaseHandler.get_handler()
        self.isLocal = isLocal
        if self.isLocal:
            self.endpoint = "http://localstack-main:4569"
            self.use_ssl = False

        self.account_db = AccountDB(endpoint=self.endpoint, use_ssl=self.use_ssl)
        self.user_db = UserDB(endpoint=self.endpoint, use_ssl=self.use_ssl)

        self.handler.register(self.account_db)
        self.handler.register(self.user_db)
