import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import List

from HavokMud.eosio.action import EOSAction

logger = logging.getLogger(__name__)


class EOSTransactionError(Exception):
    pass


class EOSTransaction(object):
    def __init__(self, actions: List[EOSAction] = None):
        if not actions:
            actions = []
        self.actions = actions
        self.memo = str(uuid.uuid4())

    def toJson(self):
        item = {
            "actions": [item.toJson() for item in self.actions]
        }
        return item

    def add(self, action: EOSAction):
        self.actions.append(action)

    def send(self, broadcast=True, sign=True, blocks_behind=3, expire_seconds=30):
        from HavokMud.startup import server_instance
        server = server_instance

        # First we need some blockchain information
        try:
            result = server.chain_api.call("get_info", openapi_validate=False)
        except Exception as e:
            logger.error("Couldn't get blockchain info: %s" % e)
            raise e

        chain_id = result.get("chain_id", None)
        ref_block_num = result.get("head_block_num", None)
        if chain_id is None or ref_block_num is None:
            raise EOSTransactionError("Invalid blockchain info")

        ref_block_num = max(0, ref_block_num - blocks_behind)

        # Now we need the timestamp of the reference block
        try:
            result = server.chain_api.call("get_block", block_num_or_id=str(ref_block_num))
        except Exception as e:
            logger.exception("result: %s" % result)
            logger.error("Couldn't get reference block: %s" % e)
            raise e

        timestamp = result.get("timestamp", None)
        ref_block_prefix = result.get("ref_block_prefix", None)
        if timestamp is None or ref_block_prefix is None:
            raise EOSTransactionError("Cannot parse reference block")

        expiration = datetime.fromisoformat(timestamp) + timedelta(seconds=expire_seconds)
        expiration = expiration.isoformat()

        transaction = {
            "expiration": expiration,
            "ref_block_num": ref_block_num,
            "ref_block_prefix": ref_block_prefix,
            "max_net_usage_words": 0,
            "max_cpu_usage_ms": 0,
            "delay_sec": 0,
            "context_free_actions": [],
            "actions": [item.toJsonBinary() for item in self.actions],
            "transaction_extensions": []
        }

        signatures = []
        if sign:
            from HavokMud.wallet import Wallet

            accounts = [item.contract for item in self.actions]
            wallets = [Wallet.load(server, account_name=item) for item in accounts]
            available_public_keys = {key for wallet in wallets for key in wallet.keys.keys()}

            # Now get the list of required public keys
            try:
                required_public_keys = server.chain_api.call("get_required_keys", transaction=transaction,
                                                             available_keys=available_public_keys)
            except Exception as e:
                raise EOSTransactionError("Couldn't get required keys: %s" % e)

            # Now we have everything we need to sign this
            try:
                signed_transaction = server.wallet_api.call("sign_transaction", transaction=transaction,
                                                            keys=required_public_keys, chain_id=chain_id)
            except Exception as e:
                raise EOSTransactionError("Couldn't sign transaction: %s" % e)

            signatures = signed_transaction.pop("signatures", [])
        else:
            signed_transaction = transaction

        if broadcast:
            # Let's send this puppy out!
            try:
                params = {
                    "signatures": signatures,
                    "compression": 0,
                    "packed_context_free_data": "",
                    "packed_trx": EOSTransaction.pack_transaction(transaction),
                }
                return server.chain_api.call("push_transaction", **params)
            except Exception as e:
                raise EOSTransactionError("Could not push transaction: %s" % e)

        signed_transaction["signatures"] = signatures
        return signed_transaction

    @staticmethod
    def pack_transaction(transaction):
        data = json.dumps(transaction)
        return "".join(map(lambda x: "%02X" % x, data.encode("utf-8")))
