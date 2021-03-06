import hashlib
import json
import logging
import os
import pickle
from functools import lru_cache
from time import sleep
from urllib.parse import urljoin

import jsonschema.validators
from jsonschema.validators import RefResolver as oldRefResolver


class newRefResolver(oldRefResolver):
    def __setstate__(self, state):
        # print("unpickling")
        self.__dict__.update(state)
        self._urljoin_cache = lru_cache(1024)(urljoin)
        self._remote_cache = lru_cache(1024)(self.resolve_from_url)

    def __getstate__(self):
        # print("pickling")
        d = dict(self.__dict__)
        d.pop("_urljoin_cache", None)
        d.pop("_remote_cache", None)
        return d


# MonkeyPatch this
jsonschema.validators.RefResolver = newRefResolver

import openapi_core
import requests
import yaml
from openapi_core.contrib.requests import RequestsOpenAPIRequest, RequestsOpenAPIResponse
from openapi_core.validation.request.validators import RequestValidator
from openapi_core.validation.response.validators import ResponseValidator

from HavokMud.api_handler import api_handler
from HavokMud.utils import log_call

logger = logging.getLogger(__name__)

swaggerDir = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "swagger"))


class SwaggerAPIError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message

    def __repr__(self):
        return "%s: %s" % (self.code, self.message)


class SwaggerAPI(object):
    name = None
    swagger_file = None
    base_url = None

    @log_call
    def __init__(self, name, swagger_file, scheme, hostname, port, path, spec_url=None):
        from HavokMud.startup import server_instance

        self.name = name
        (base_file, _) = os.path.splitext(swagger_file)
        self.swagger_file = os.path.join(swaggerDir, swagger_file)
        self.pickle_file = os.path.join(swaggerDir, base_file + ".pickle")
        self.base_url = "%s://%s:%s%s" % (scheme, hostname, port, path)
        if spec_url:
            self.spec_url = spec_url
        else:
            self.spec_url = self.base_url
        if not self.spec_url.endswith("/"):
            self.spec_url += "/"
        self.response = None

        logger.info("Attempting to load encrypted pickled API spec for %s" % name)
        loaded = False
        if os.path.exists(self.pickle_file):
            pickle_time = os.path.getmtime(self.pickle_file)
            swagger_time = os.path.getmtime(self.swagger_file)
            if swagger_time >= pickle_time:
                logger.info("Alas, the swagger file is newer than the pickled API")
            else:
                try:
                    with open(self.pickle_file, "r") as f:
                        encrypted = f.read()
                    pickled = server_instance.encryption.decrypt(encrypted)
                    with open(self.pickle_file + ".sha512", "r") as f:
                        digest = f.read()
                    calc_digest = hashlib.sha512(pickled).hexdigest()
                    if digest != calc_digest:
                        raise ValueError("Pickle file's SHA512 does not match!")

                    self.api_spec = pickle.loads(pickled)
                    loaded = True
                except Exception as e:
                    logger.error("Exception unpickling: %s" % e)
                    # raise e

        if not loaded:
            logger.info("Loading swagger file: %s" % swagger_file)
            with open(self.swagger_file, "r") as f:
                self.swagger_object = yaml.safe_load(f.read())

            logger.info("Creating API spec for %s" % name)
            count = 30
            while count and not loaded:
                try:
                    self.api_spec = openapi_core.create_spec(self.swagger_object, self.spec_url)
                    loaded = True
                except Exception as e:
                    count -= 1
                    logger.exception("Belched on create_spec, %s retries left: %s" % (count, e))
                    sleep(1.0)

            if not loaded:
                raise Exception("Can't load API Spec for %s" % name)

            try:
                logger.info("Writing encrypted pickled API spec for %s" % name)
                pickled = pickle.dumps(self.api_spec, protocol=pickle.HIGHEST_PROTOCOL)
                encrypted = server_instance.encryption.encrypt(pickled)
                with open(self.pickle_file, "w") as f:
                    f.write(encrypted)
                digest = hashlib.sha512(pickled).hexdigest()
                with open(self.pickle_file + ".sha512", "w") as f:
                    f.write(digest)
            except Exception as e:
                os.unlink(self.pickle_file)
                os.unlink(self.pickle_file + ".sha512")
                raise e

        self.methods = {os.path.basename(key): {"path": key, "object": value}
                        for (key, value) in self.api_spec.paths.items()}
        self.request_validator = RequestValidator(self.api_spec)
        self.response_validator = ResponseValidator(self.api_spec)
        logger.info("Finished loading API for %s" % name)

    @log_call
    def call(self, method, *args, **kwargs):
        timeout = kwargs.pop("timeout", 10)
        openapi_validate = kwargs.pop("openapi_validate", True)

        if method not in self.methods:
            raise NotImplementedError("Method %s not implemented by %s API" % (method, self.name))

        payload = {}
        if args:
            if len(args) == 1:
                payload = args[0]
            else:
                payload = list(args)
        elif kwargs:
            payload = kwargs

        method_item = self.methods.get(method, {})
        _object = method_item.get("object", None)
        if _object is None:
            operation = "POST"
        else:
            operation = list(_object.operations.keys()).pop()

        params = {
            "method": operation.upper(),
            "url": self.base_url + method_item.get("path", ""),
            "headers": {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Connection": "close",
            },
        }
        if payload is not None:
            params["data"] = json.dumps(payload)

        # Generate a request
        request = requests.Request(**params)

        # Validate the request
        if openapi_validate:
            openapi_request = RequestsOpenAPIRequest(request)
            result = self.request_validator.validate(openapi_request)
            result.raise_for_errors()

        response = api_handler.send(request, timeout)
        self.response = response
        try:
            message = response.json()
        except Exception as e:
            logger.error("Exception decoding response: %s" % e)
            logger.debug("length: %s, headers: %s" % (len(response.content), response.headers))
            with open("/tmp/failedresponse", "wb") as f:
                f.write(response.content)
            raise SwaggerAPIError(500, response.content)

        if int(response.status_code / 100) != 2:
            logger.error("Error %s on request %s" % (response.status_code, params))
            raise SwaggerAPIError(response.status_code, message)

        # Validate the response
        if openapi_validate:
            openapi_response = RequestsOpenAPIResponse(response)
            # noinspection PyUnboundLocalVariable
            result = self.response_validator.validate(openapi_request, openapi_response)
            result.raise_for_errors()

        return message
