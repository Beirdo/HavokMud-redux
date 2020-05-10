import logging

from HavokMud.eosio.abi import EOSAbi

logger = logging.getLogger(__name__)


class EOSActionError(Exception):
    pass


class EOSAction(object):
    def __init__(self, contract: str, action_name: str,
                 authorization: list, *args, **kwargs):
        self.contract = contract
        self.action_name = action_name
        self.authorization = authorization
        self.abi = EOSAbi.lookup(contract)

        actions = self.abi.get("actions", [])
        action = actions.get(self.action_name, None)
        if action is None:
            raise KeyError("Can't find action %s" % self.action_name)

        self.type_name = action.get("type", None)
        if not self.type_name:
            raise KeyError("No type defined for action %s" % self.action_name)

        action_args = {}
        if len(args) == 1:
            action_args = args[0]
        elif args:
            action_args = list(args)
        elif kwargs:
            action_args = dict(kwargs)

        self.action_args = action_args

    def toJson(self):
        item = {
            "account": self.contract,
            "name": self.action_name,
            "authorization": [item.toJson() for item in self.authorization],
            "data": self.action_args,
        }
        return item

    def toJsonBinary(self):
        item = self.toJson()
        item["hex_data"] = self.serialize()
        return item

    def serialize(self):
        return self.abi.serialize(self.type_name, self.action_args)

    def deserialize(self, data: str):
        return self.abi.deserialize(self.type_name, data)
