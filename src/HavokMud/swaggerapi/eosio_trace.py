import logging

from HavokMud.swaggerapi import SwaggerAPI

logger = logging.getLogger(__name__)


class EOSTraceAPI(SwaggerAPI):
    def __init__(self, config):
        apiConfig = config.get("eos_trace_api_plugin", {})
        if not apiConfig:
            apiConfig = {}
        args = [
            apiConfig.get("scheme", "http"),
            apiConfig.get("hostname", "eosio.havokmud"),
            apiConfig.get("port", 8000),
        ]
        SwaggerAPI.__init__("EOSTrace", "trace_api.swagger.yaml", *args, "/v1")
