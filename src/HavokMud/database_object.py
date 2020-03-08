import logging

logger = logging.getLogger(__name__)


class DatabaseObject(object):
    __fixed_fields__ = []
    __database__ = None

    def __setattr__(self, name, value):
        self.__dict__[name] = value

    def __getattr__(self, name):
        return self.__dict__.get(name, None)

    # noinspection PyTypeChecker
    def to_dict(self):
        return dict(filter(lambda x: x[0] not in self.__fixed_fields__, self.__dict__.items()))

    def from_dict(self, newdata):
        oldfields = set(self.__dict__.keys())
        newfields = set(newdata.keys()) | set(self.__fixed_fields__)
        removefields = oldfields - newfields
        # noinspection PyTypeChecker
        newdict = dict(filter(lambda x: x[0] not in removefields, self.__dict__.items()))
        newdict.update(newdata)
        self.__dict__ = newdict

    def load_from_db(self, **key):
        if not self.__database__:
            raise ValueError("Database not defined in class %s" % self.__class__.__name__)

        data = self.__database__.get_item(key)
        self.from_dict(data)

    def save_to_db(self):
        if not self.__database__:
            raise ValueError("Database not defined in class %s" % self.__class__.__name__)

        self.__database__.put_item(self.to_dict())