import json
import logging
import os
import sys

import openapi_core
import requests
import yaml
from openapi_core.contrib.requests import RequestsOpenAPIRequest, RequestsOpenAPIResponse
from openapi_core.validation.request.validators import RequestValidator
from openapi_core.validation.response.validators import ResponseValidator

from HavokMud.api_handler import api_handler

logger = logging.getLogger(__name__)

baseDir = os.path.realpath(os.path.join(sys.argv[0], "..", ".."))
swaggerDir = os.path.join(baseDir, "src", "HavokMud", "swagger")


class SwaggerAPI(object):
    name = None
    swagger_file = None
    base_url = None

    def __init__(self, name, swagger_file, scheme, hostname, port, path):
        self.name = name
        self.swagger_file = os.path.join(swaggerDir, swagger_file)
        self.base_url = "%s://%s:%s%s" % (scheme, hostname, port, path)

        logger.info("Loading swagger file: %s" % swagger_file)
        with open(self.swagger_file, "r") as f:
            self.swagger_object = yaml.safe_load(f.read())

        logger.info("Creating API spec for %s" % name)
        self.api_spec = openapi_core.create_spec(self.swagger_object, self.base_url)
        self.methods = {os.path.basename(key): {"path": key, "object": value}
                        for (key, value) in self.api_spec.paths.items()}
        self.request_validator = RequestValidator(self.api_spec)
        self.response_validator = ResponseValidator(self.api_spec)
        logger.info("Finished loading API for %s" % name)

    def call(self, method, timeout, *args, **kwargs):
        if method not in self.methods:
            raise NotImplementedError("Method %s not implemented by %s API" % (method, self.name))

        payload = None
        if args:
            if len(args) == 1:
                payload = args[0]
            else:
                payload = list(args)
        elif kwargs:
            payload = kwargs

        params = {
            "method": 'POST',
            "url": self.base_url + self.methods.get("path", "/"),
            "headers": {
                "Content-Type": "application/json",
            },
        }
        if payload is not None:
            params["body"] = json.dumps(payload)

        # Generate a request
        request = requests.Request(**params)

        # Validate the request
        openapi_request = RequestsOpenAPIRequest(request)
        result = self.request_validator.validate(openapi_request)
        result.raise_for_errors()

        response = api_handler.send(request, timeout)

        openapi_response = RequestsOpenAPIResponse(response)
        result = self.response_validator.validate(openapi_response)
        result.raise_for_errors()

        return response.json()
