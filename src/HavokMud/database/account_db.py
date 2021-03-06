import logging

from HavokMud.database.base import Database

logger = logging.getLogger(__name__)


class AccountDB(Database):
    table = "havokmud_accounts"
    db_attributes = [
        {
            'AttributeName': "email",
            'AttributeType': "S"
        }
    ]

    db_key_schema = [
        {
            'AttributeName': "email",
            'KeyType': "HASH"
        }
    ]
