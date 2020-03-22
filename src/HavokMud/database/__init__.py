from .account_db import AccountDB
from .handler import DatabaseHandler
from .user_db import UserDB


class Databases(object):
    def __init__(self, config):
        self.handler = DatabaseHandler.get_handler()
        self.config = config

        dynamo_config = config.get("dynamodb", {})
        self.endpoint = dynamo_config.get("endpoint", None)
        self.use_ssl = dynamo_config.get("useSsl", True)

        self.account_db = AccountDB(endpoint=self.endpoint, use_ssl=self.use_ssl)
        self.user_db = UserDB(endpoint=self.endpoint, use_ssl=self.use_ssl)

        self.handler.register(self.account_db)
        self.handler.register(self.user_db)
