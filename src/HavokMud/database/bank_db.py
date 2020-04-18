import logging

from HavokMud.database.base import Database

logger = logging.getLogger(__name__)


class BankDB(Database):
    table = "havokmud_banks"
    db_attributes = [
        {
            'AttributeName': "name",
            'AttributeType': "S"
        }
    ]

    db_key_schema = [
        {
            'AttributeName': "name",
            'KeyType': "HASH"
        }
    ]
