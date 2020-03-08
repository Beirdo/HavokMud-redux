import logging

from HavokMud.database import Database

logger = logging.getLogger(__name__)


class AccountDB(Database):
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
