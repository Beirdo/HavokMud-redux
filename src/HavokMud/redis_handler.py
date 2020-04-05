import logging
import stackless
from redis import Redis

logger = logging.getLogger(__name__)


class RedisRequest(object):
    def __init__(self, command, *args, **kwargs):
        self.command = command
        self.args = args
        self.kwargs = kwargs
        self.channel = stackless.channel()


class RedisHandler(object):
    def __init__(self, config):
        self.in_channel = stackless.channel()

        self.config = config
        redis_config = self.config.get("redis", {})
        self.redis = Redis(**redis_config)

        stackless.tasklet(self.redis_loop)()

    def redis_loop(self):
        while True:
            request = self.in_channel.receive()
            stackless.tasklet(self.redis_handle)(request)

    def redis_handle(self, request):
        retval = None

        command = request.command
        args = request.args
        kwargs = request.kwargs

        func = getattr(self.redis, command, None)
        if func and hasattr(func, "__call__"):
            retval = func(*args, **kwargs)

        request.channel.send(retval)

    def do_command(self, command, *args, **kwargs):
        request = RedisRequest(command, *args, **kwargs)
        self.in_channel.send(request)
        return request.channel.receive()
