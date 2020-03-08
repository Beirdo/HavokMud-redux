from .account_db import AccountDB
from .user_db import UserDB


class Databases(object):
    isLocal = False
    endpoint = None

    def __init__(self, isLocal=False):
        self.isLocal = isLocal
        if self.isLocal:
            self.endpoint = "http://localhost:4569"

        self.account_db = AccountDB(self.endpoint)
        self.user_db = UserDB(self.endpoint)