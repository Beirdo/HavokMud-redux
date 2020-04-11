import logging

from HavokMud.swaggerapi import SwaggerAPI

logger = logging.getLogger(__name__)


class EOSWalletAPI(SwaggerAPI):
    def __init__(self, config):
        apiConfig = config.get("eos_wallet_plugin", {})
        if not apiConfig:
            apiConfig = {}
        args = [
            apiConfig.get("scheme", "http"),
            apiConfig.get("hostname", "eosio.havokmud"),
            apiConfig.get("port", 6666),
        ]
        SwaggerAPI.__init__("EOSWallet", "wallet.swagger.yaml", *args, "/v1")
