import logging

logger = logging.getLogger(__name__)


class DatabaseObject(object):
    __fixed_fields__ = []
    __database__ = None

    def __init__(self):
        self.__fixed_fields__.extend(["__fixed_fields__", "__database__"])

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

    # noinspection PyTypeChecker
    def to_dict(self):
        return dict(filter(lambda x: x[0] not in self.__fixed_fields__, self.__dict__.items()))

    def from_dict(self, newdata):
        # logger.debug("new data: %s" % newdata)
        oldfields = set(self.__dict__.keys())
        newfields = set(newdata.keys()) | set(self.__fixed_fields__)
        removefields = oldfields - newfields
        # logger.debug("Removing fields: %s" % removefields)

        # noinspection PyTypeChecker
        newdict = dict(filter(lambda x: x[0] not in removefields, self.__dict__.items()))
        newdict.update(newdata)
        # logger.debug("newdict: %s" % newdict)
        for (key, value) in newdict.items():
            setattr(self, key, value)
        for field in removefields:
            delattr(self, field)
        # logger.debug("finished: %s" % dict(self.__dict__))

    def load_from_db(self, **key):
        if not self.__database__:
            raise ValueError("Database not defined in class %s" % self.__class__.__name__)

        # logger.debug("Dir: %s" % dir(self.__database__))
        data = self.__database__.handler.send_request(self.__database__.table, "get_item", key)
        self.from_dict(data)

    def save_to_db(self):
        if not self.__database__:
            raise ValueError("Database not defined in class %s" % self.__class__.__name__)

        self.__database__.handler.send_request(self.__database__.table, "put_item", self.to_dict())
