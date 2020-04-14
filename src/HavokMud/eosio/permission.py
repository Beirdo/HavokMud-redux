import logging

logger = logging.getLogger(__name__)


class EOSPermission(object):
    def __init__(self, actor, permission):
        self.actor = actor
        self.permission = permission

    def toJson(self):
        return {
            "actor": self.actor,
            "permission": self.permission,
        }