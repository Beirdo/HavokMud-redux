import logging

from HavokMud.swaggerapi import SwaggerAPI

logger = logging.getLogger(__name__)


class EOSDBSizeAPI(SwaggerAPI):
    def __init__(self, config):
        apiConfig = config.get("eos_db_size_plugin", {})
        if not apiConfig:
            apiConfig = {}
        args = [
            apiConfig.get("scheme", "http"),
            apiConfig.get("hostname", "eosio.havokmud"),
            apiConfig.get("port", 8000),
        ]
        SwaggerAPI.__init__(self, "EOSDBSize", "db_size.swagger.yaml", *args, "/v1",
                            "https://eosio.github.io/schemata/v2.0/oas")
