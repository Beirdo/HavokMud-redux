import logging

from HavokMud.swaggerapi import SwaggerAPI

logger = logging.getLogger(__name__)


class EOSProducerAPI(SwaggerAPI):
    def __init__(self, config):
        apiConfig = config.get("eos_producer_plugin", {})
        if not apiConfig:
            apiConfig = {}
        args = [
            apiConfig.get("scheme", "http"),
            apiConfig.get("hostname", "eosio.havokmud"),
            apiConfig.get("port", 8000),
        ]
        SwaggerAPI.__init__(self, "EOSProducer", "producer.swagger.yaml", *args, "/v1")
