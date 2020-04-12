from .account_db import AccountDB
from .handler import DatabaseHandler
from .settings_db import SettingsDB
from .user_db import UserDB


class Databases(object):
    def __init__(self, config):
        self.handler = DatabaseHandler.get_handler()
        self.config = config

        self.account_db = AccountDB(self.config)
        self.user_db = UserDB(self.config)
        self.settings_db = SettingsDB(self.config)

        self.handler.register(self.account_db)
        self.handler.register(self.user_db)
        self.handler.register(self.settings_db)
