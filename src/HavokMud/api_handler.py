import logging
import stackless

import requests

logger = logging.getLogger(__name__)


class APIRequest(object):
    def __init__(self, request, timeout):
        self.request = request
        self.timeout = timeout
        self.channel = stackless.channel()


class APIHandler(object):
    def __init__(self):
        self.session = requests.Session()
        self.in_channel = stackless.channel()

        stackless.tasklet(self.handler_loop)()

    def handler_loop(self):
        while True:
            request = self.in_channel.receive()
            stackless.tasklet(self.api_request)(request)

    def api_request(self, request):
        prepped = self.session.prepare_request(request.request)
        try:
            response = self.session.send(prepped, timeout=request.timeout)
        except Exception as e:
            response = {"exception": e}
        request.channel.send(response)

    def send(self, request, timeout):
        item = APIRequest(request, timeout)
        self.in_channel.send(item)
        item = request.channel.receive()
        if isinstance(item, dict):
            exception = item.get("exception", None)
            if exception:
                raise exception
        return item


api_handler = APIHandler()
