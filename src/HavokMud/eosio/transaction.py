import codecs
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import List

from HavokMud.eosio.abi import EOSAbi
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
            result = server.chain_api.call("get_block", block_num_or_id=str(ref_block_num),
                                           openapi_validate=False)
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
            "delay_sec": 5,
            "context_free_actions": [],
            "actions": [item.toJsonBinary() for item in self.actions],
            "transaction_extensions": []
        }

        presigned_transaction = {
            "transaction": transaction,
            "signatures": [],
            "context_free_data": [],
        }

        if sign:
            from HavokMud.wallet import Wallet

            # Need keys for the contract owners
            accounts = {item.contract for item in self.actions}
            # Also need keys for the permissions used in the action authorization
            accounts |= {item.actor for action in self.actions
                         for item in action.authorization}
            logger.info("Need keys for: %s" % accounts)
            wallets = [Wallet.load(account_name=item) for item in accounts]
            available_public_keys = {key: wallet for wallet in wallets for key in wallet.keys.keys()}

            # Now get the list of required public keys
            try:
                required_public_keys = server.chain_api.call("get_required_keys", transaction=transaction,
                                                             available_keys=list(available_public_keys.keys()),
                                                             openapi_validate=False)
            except Exception as e:
                raise EOSTransactionError("Couldn't get required keys: %s" % e)

            required_public_keys = required_public_keys.get("required_keys", [])

            logger.info("Available keys: %s" % available_public_keys)
            logger.info("Required keys: %s" % required_public_keys)

            # Unlock the wallets that are needed
            wallets = list(filter(None, {available_public_keys.get(key, None) for key in required_public_keys}))
            logger.info("Wallets required: %s" % wallets)
            for wallet in wallets:
                wallet.unlock()

            # Now we have everything we need to sign this
            try:
                signed_transaction = server.wallet_api.call("sign_transaction", transaction=presigned_transaction,
                                                            keys=required_public_keys, chain_id=chain_id,
                                                            openapi_validate=False)
            except Exception as e:
                raise EOSTransactionError("Couldn't sign transaction: %s" % e)

            # relock the wallets
            for wallet in wallets:
                wallet.lock()
        else:
            signed_transaction = presigned_transaction

        signatures = signed_transaction.get("signatures", [])
        transaction = presigned_transaction.get("transaction", {})

        if broadcast:
            # Let's send this puppy out!
            try:
                params = {
                    "signatures": signatures,
                    "compression": False,
                    "packed_context_free_data": "",
                    "packed_trx": EOSTransaction.pack_transaction(transaction),
                }
                return server.chain_api.call("send_transaction", **params)
            except Exception as e:
                raise EOSTransactionError("Could not send transaction: %s" % e)

        return signed_transaction

    @staticmethod
    def pack_transaction(transaction):
        actions = transaction.get("actions", [])
        for action in actions:
            action['data'] = action.pop("hex_data", "")
        abi = EOSAbi.lookup("transaction")
        return abi.serialize("transaction", transaction)
