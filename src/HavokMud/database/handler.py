import logging
import stackless

from HavokMud.utils import log_call

logger = logging.getLogger(__name__)


class DatabaseRequest(object):
    def __init__(self, table_name, command, *args, **kwargs):
        self.table_name = table_name
        self.command = command
        self.args = list(args)
        self.kwargs = dict(kwargs)
        self.response_channel = stackless.channel()


database_handler = None


class DatabaseHandler(object):
    table_map = {}

    def __init__(self):
        self.in_channel = stackless.channel()
        stackless.tasklet(self.handler_loop)()

    @staticmethod
    def get_handler():
        global database_handler
        if not database_handler:
            database_handler = DatabaseHandler()
        return database_handler

    def register(self, instance):
        self.table_map[instance.table] = instance
        instance.handler = self

    def handler_loop(self):
        while True:
            item = self.in_channel.receive()
            stackless.tasklet(self.database_tasklet)(item)

    def database_tasklet(self, item):
        logger.debug("Item: %s" % item.__dict__)
        response_channel = item.response_channel
        table_name = item.table_name
        response = None
        if table_name:
            db = self.table_map.get(table_name, None)
            if db:
                func = getattr(db, item.command, None)
                if func and hasattr(func, "__call__"):
                    # logger.debug("Func: %s, args: %s, kwargs: %s" % (func, item.args, item.kwargs))
                    response = func(*item.args, **item.kwargs)

        logger.debug("Response: %s" % response)
        response_channel.send(response)

    @log_call(censor=["all_args", "!1", "!2", "all_kwargs"])
    def send_request(self, table_name, command, *args, **kwargs):
        request = DatabaseRequest(table_name, command, *args, **kwargs)
        self.in_channel.send(request)
        response = request.response_channel.receive()
        return response
