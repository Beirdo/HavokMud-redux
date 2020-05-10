import logging

from HavokMud.database.base import Database

logger = logging.getLogger(__name__)


class SystemDB(Database):
    table = "havokmud_system_wallets"
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
