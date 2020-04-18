import logging

from HavokMud.database.base import Database

logger = logging.getLogger(__name__)


class SettingsDB(Database):
    table = "havokmud_settings"
    db_attributes = [
        {
            'AttributeName': "key",
            'AttributeType': "S"
        }
    ]

    db_key_schema = [
        {
            'AttributeName': "key",
            'KeyType': "HASH"
        }
    ]
