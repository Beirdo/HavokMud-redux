import json
import logging
import uuid
from threading import Lock

from HavokMud.database_object import DatabaseObject
from HavokMud.jinjaprocessor import jinja_processor
from HavokMud.logging_support import AccountLogMessage

logger = logging.getLogger(__name__)


class Settings(DatabaseObject):
    __fixed_fields__ = ["server"]
    __database__ = None

    def __init__(self, server, key, value=None):
        DatabaseObject.__init__(self)
        self.server = server
        self.__database__ = self.server.dbs.settings_db

        self.key = key
        self.value = value

    @staticmethod
    def lookup_by_key(server, key):
        # Look this up in DynamoDB
        item = Settings(server, key)

        # if not in dynamo: will return with empty value field
        item.load_from_db(key=key)

        return item

    @staticmethod
    def get_all_settings(server):
        return [Settings(server, key=item.get("key", None), value=item.get("value", None))
                for item in server.dbs.settings_db.get_all()]
