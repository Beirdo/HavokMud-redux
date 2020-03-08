import logging

from HavokMud.database import Database

logger = logging.getLogger(__name__)


class UserDB(Database):
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
