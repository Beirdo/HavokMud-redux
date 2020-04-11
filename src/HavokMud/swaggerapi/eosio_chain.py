import logging

from HavokMud.swaggerapi import SwaggerAPI

logger = logging.getLogger(__name__)


class EOSChainAPI(SwaggerAPI):
    def __init__(self, config):
        apiConfig = config.get("eos_chain_plugin", {})
        if not apiConfig:
            apiConfig = {}
        args = [
            apiConfig.get("scheme", "http"),
            apiConfig.get("hostname", "eosio.havokmud"),
            apiConfig.get("port", 8000),
        ]
        SwaggerAPI.__init__("EOSChain", "chain.swagger.yaml", *args, "/v1")
