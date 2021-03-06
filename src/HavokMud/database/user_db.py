import logging

from HavokMud.database.base import Database

logger = logging.getLogger(__name__)


class UserDB(Database):
    table = "havokmud_players"
    db_attributes = [
        {
            'AttributeName': "email",
            'AttributeType': "S"
        },
        {
            'AttributeName': 'player_name',
            'AttributeType': "S"
        }
    ]

    db_key_schema = [
        {
            'AttributeName': "email",
            'KeyType': "HASH"
        },
        {
            'AttributeName': 'player_name',
            'KeyType': 'RANGE'
        }
    ]
