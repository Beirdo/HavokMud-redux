import logging
from copy import deepcopy, copy

logger = logging.getLogger(__name__)


class DatabaseObject(object):
    __fixed_fields__ = []
    __database__ = None
    __real_class__ = None

    def __init__(self):
        from HavokMud.startup import server_instance
        self.__fixed_fields__.extend(["__fixed_fields__", "__database__", "__real_class__"])
        self.__real_class__ = self.__class__
        self.server = server_instance

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

    # noinspection PyTypeChecker
    def to_dict(self):
        return dict(filter(lambda x: x[0] not in self.__fixed_fields__, self.__dict__.items()))

    def from_dict(self, newdata):
        # logger.debug("new data: %s" % newdata)
        fixed_fields = set(self.__fixed_fields__)
        newdata = dict(filter(lambda x: x[0] not in fixed_fields, newdata.items()))
        # logger.debug("new data: %s" % newdata)
        oldfields = set(self.__dict__.keys())
        newfields = set(newdata.keys()) | fixed_fields
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
        # logger.debug("dict: %s" % self.__dict__)
        return self.__real_class__(other=self)

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

    def get_all(self):
        if not self.__database__:
            raise ValueError("Database not defined in class %s" % self.__class__.__name__)

        rows = self.__database__.handler.send_request(self.__database__.table, "get_all")
        # logger.debug("rows: %s" % rows)
        # logger.debug("self: %s (%s)" % (self, self.__dict__))
        return [self.from_dict(row) for row in rows if row]
