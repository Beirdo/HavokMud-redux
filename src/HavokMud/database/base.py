import logging
from decimal import Decimal

import boto3

logger = logging.getLogger(__name__)


def _dict_to_dynamodb(func):
    def wrapper(*args, **kwargs):
        args = list(args)
        data = args.pop(1)
        logger.debug("raw: %s" % data)
        dynamo_data = {key: _convert_to_dynamodb(value) for (key, value) in data.items()}
        args.insert(1, dynamo_data)
        logger.debug("converted: %s" % dynamo_data)
        return func(*args, **kwargs)

    return wrapper


def _convert_to_dynamodb(item):
    if item is True or item is False:
        return {'BOOL': item}
    if item is None:
        return {'NULL': True}
    if isinstance(item, dict):
        return {'M': {key: _convert_to_dynamodb(value) for (key, value) in item.items()}}
    if isinstance(item, (list, tuple, set)):
        return {'L': [_convert_to_dynamodb(value) for value in item]}
    if isinstance(item, (float, int, Decimal)):
        return {'N': str(item)}
    if isinstance(item, str):
        return {'S': item}
    if isinstance(item, bytes):
        return {'B': item}
    return {'S': str(item)}


def _dynamodb_to_dict(func):
    def wrapper(*args, **kwargs):
        dynamo_data = func(*args, **kwargs)
        logger.debug("Raw: %s" % dynamo_data)
        data = _convert_row_from_dynamodb(dynamo_data)
        logger.debug("Converted: %s" % data)
        return data

    return wrapper


def _dynamodb_to_array(func):
    def wrapper(*args, **kwargs):
        dynamo_data = func(*args, **kwargs)
        data = [_convert_row_from_dynamodb(row) for row in dynamo_data]
        return data

    return wrapper


def _convert_row_from_dynamodb(row):
    return {key: _convert_field_from_dynamodb(value) for (key, value) in row.items()}


def _convert_field_from_dynamodb(item):
    item = list(item.items())
    item = item.pop()
    (key, value) = item
    if key == 'S' or key == 'B' or key == 'BOOL' or key == 'SS' or key == 'BS':
        return value
    if key == 'NULL':
        return None
    if key == 'M':
        return _convert_row_from_dynamodb(value)
    if key == 'L':
        return [_convert_field_from_dynamodb(value2) for value2 in value]
    if key == 'N':
        return _convert_numeric(value)
    if key == 'NS':
        return [_convert_numeric(value2) for value2 in value]


def _convert_numeric(value):
    number = float(value)
    if int(number) == number:
        number = int(number)
    return number


class Database(object):
    table = None
    endpoint = None
    region = None
    db_attributes = None
    db_key_schema = None
    db_local_secondary_indexes = None
    db_global_secondary_indexes = None
    db_billing_mode = None
    db_provisioned_throughput = None
    handler = None

    def __init__(self, config):
        self.config = config

        self.region = self.config.get("mud", {}).get("region", "us-east-1")

        dynamodb_config = self.config.get("dynamodb", {})
        self.endpoint = dynamodb_config.get("endpoint", None)
        self.use_ssl = dynamodb_config.get("useSsl", True)

        if not self.table:
            raise ValueError("Table not defined in class %s" % self.__class__.__name__)

        self.session = boto3.session.Session(region_name=self.region)
        self.dynamodb = self.session.client('dynamodb', endpoint_url=self.endpoint, use_ssl=self.use_ssl)
        self.create_table()

    def create_table(self):
        create = False
        try:
            table_desc = self.dynamodb.describe_table(TableName=self.table)
            status = table_desc.get("Table", {}).get("TableStatus", None)
            if status == 'ACTIVE':
                return
        except self.dynamodb.exceptions.ResourceNotFoundException as e:
            create = True

        if create:
            if not self.db_attributes:
                raise ValueError("DB Attributes missing in class %s" % self.__class__.__name__)

            if not self.db_key_schema:
                raise ValueError("DB Key Schema missing in class %s" % self.__class__.__name__)

            if not self.db_billing_mode:
                self.db_billing_mode = "PAY_PER_REQUEST"

            table_definition = {
                "TableName": self.table,
                "AttributeDefinitions": self.db_attributes,
                "KeySchema": self.db_key_schema,
                "BillingMode": self.db_billing_mode,
            }

            if self.db_billing_mode == "PROVISIONED":
                table_definition['ProvisionedThroughput'] = self.db_provisioned_throughput

            if self.db_local_secondary_indexes:
                table_definition["LocalSecondaryIndexes"] = self.db_local_secondary_indexes

            if self.db_global_secondary_indexes:
                table_definition["GlobalSecondaryIndexes"] = self.db_global_secondary_indexes

            self.dynamodb.create_table(**table_definition)

        waiter = self.dynamodb.get_waiter('table_exists')
        waiter.wait(TableName=self.table)

    @_dynamodb_to_dict
    @_dict_to_dynamodb
    def get_item(self, keys):
        try:
            return self.dynamodb.get_item(TableName=self.table, Key=keys, ConsistentRead=True).get("Item", {})
        except Exception as e:
            return {}

    @_dict_to_dynamodb
    def put_item(self, data):
        try:
            self.dynamodb.put_item(TableName=self.table, Item=data)
        except Exception:
            pass

    @_dynamodb_to_array
    def get_all(self):
        items = []
        paginator = self.dynamodb.get_paginator("scan")

        try:
            for page in paginator.paginate(TableName=self.table):
                items.extend(page.get("Items", []))
            return items
        except Exception as e:
            logger.error("%s.get_all failed: %s" % (self.__class__.__name__, e))
            return []