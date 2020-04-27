import codecs
import json
import logging
import re
import struct
from datetime import datetime
from enum import Enum
from functools import partial
from threading import Lock

import base58
from Crypto.Hash import RIPEMD160

logger = logging.getLogger(__name__)


class EOSAbiError(Exception):
    pass


abi_map = {}
abi_map_lock = Lock()


class EOSAbiState(object):
    def __init__(self, in_state=None):
        if in_state:
            self.allow_extensions = in_state.allow_extensions
            self.skipped_binary_extensions = in_state.skipped_binary_extensions
        else:
            self.allow_extensions = True
            self.skipped_binary_extensions = False


class EOSAbiType(object):
    def __init__(self, name, base_name=None, fields=None, alias=None, array_of=None,
                 optional_of=None, extension_of=None, pack_=None, hex_digits=None, variant=None):
        self.name = name
        self.base_name = base_name
        self.base_type = None
        self.fields = fields
        self.alias_of = alias
        self.array_of = array_of
        self.optional_of = optional_of
        self.extension_of = extension_of
        self.pack_ = pack_
        self.hex_digits = hex_digits
        self.variant = variant

        if self.array_of:
            self.serializer = self._serialize_array
            self.deserializer = self._deserialize_array
        elif self.optional_of:
            self.serializer = self._serialize_optional
            self.deserializer = self._deserialize_optional
        elif self.extension_of:
            self.serializer = self._serialize_extension
            self.deserializer = self._deserialize_extension
        elif self.variant:
            self.serializer = self._serialize_variant
            self.deserializer = self._deserialize_variant
        elif self.fields:
            self.serializer = self._serialize_struct
            self.deserializer = self._deserialize_struct
        elif self.pack_:
            self.serializer = partial(self._serialize_packed, self.pack_)
            self.deserializer = partial(self._deserialize_packed, self.pack_)
        elif self.hex_digits:
            self.serializer = partial(self._serialize_hex_string, self.hex_digits)
            self.deserializer = partial(self._deserialize_hex_string, self.hex_digits)
        else:
            self.serializer = getattr(self, "_serialize_%s" % name, None)
            self.deserializer = getattr(self, "_deserialize_%s" % name, None)

    @staticmethod
    def get(types: dict, new_types: dict, name):
        type_ = types.get(name, None)
        if type_ and type_.alias_of:
            new_type = EOSAbiType.get(types, new_types, type_.alias_of)
            new_types.update({new_type.name: new_type})
            return new_type
        if type_:
            return type_

        if name.endswith("[]"):
            new_type = EOSAbiType(name, array_of=EOSAbiType.get(types, new_types, name[:-2]))
            new_types.update({new_type.name: new_type})
            return new_type

        if name.endswith("?"):
            new_type = EOSAbiType(name, optional_of=EOSAbiType.get(types, new_types, name[:-1]))
            new_types.update({new_type.name: new_type})
            return new_type

        if name.endswith("$"):
            new_type = EOSAbiType(name, extension_of=EOSAbiType.get(types, new_types, name[:-1]))
            new_types.update({new_type.name: new_type})
            return new_type

        logger.error("Unknown type: %s" % name)
        return None

    def _serialize_packed(self, pack_, state: EOSAbiState, buf: bytearray, data):
        buf += struct.pack(pack_, data)

    def _deserialize_packed(self, pack_, buf: bytearray, state: EOSAbiState):
        length = struct.calcsize(pack_)
        slice_ = buf[:length]
        buf = buf[length:]
        (result,) = struct.unpack(pack_, slice_)
        return result

    def _serialize_varuint32(self, state: EOSAbiState, buf: bytearray, data: int):
        while True:
            if data >> 7:
                buf.append(0x80 | (data & 0x7F))
                data >>= 7
            else:
                buf.append(data & 0x7F)
                return

    def _deserialize_varuint32(self, buf: bytearray, state: EOSAbiState):
        value = 0
        bit = 0
        while True:
            b = buf.pop(0)
            value |= (b & 0x7F) << bit
            bit += 7
            if not (b & 0x80):
                return value

    def _serialize_varint32(self, state: EOSAbiState, buf: bytearray, data: int):
        self._serialize_varuint32(state, buf, (data << 1) ^ (data >> 31))

    def _deserialize_varint32(self, buf: bytearray, state: EOSAbiState):
        value = self._deserialize_varuint32(buf, state)
        if value & 1:
            return ((~value) >> 1) | 0x80000000
        else:
            return value >> 1

    def _serialize_uint128(self, state: EOSAbiState, buf: bytearray, data: int):
        (hi, lo) = divmod(data, 1 << 64)
        self._serialize_packed("<Q", state, buf, lo)
        self._serialize_packed("<Q", state, buf, hi)

    def _deserialize_uint128(self, buf: bytearray, state: EOSAbiState):
        value = self._deserialize_packed("<Q", buf, state)
        value |= (self._deserialize_packed("<Q", buf, state) << 64)
        return value

    def _serialize_int128(self, state: EOSAbiState, buf: bytearray, data: int):
        if data < 0:
            data = (~(0 - data)) & ((1 << 128) - 1)

        self._serialize_uint128(state, buf, data)

    def _deserialize_int128(self, buf: bytearray, state: EOSAbiState):
        value = self._deserialize_uint128(buf, state)
        if value & (1 << 127):
            value = 0 - ((value - 1) ^ ((1 << 128) - 1))
        return value

    def _serialize_hex_string(self, digits: int, state: EOSAbiState, buf: bytearray, data: str):
        if len(data) != digits * 2:
            raise ValueError("Can't pack %s, incorrect length (is %s, should be %s)" % (data, len(data), digits * 2))

        buf += codecs.decode(data.encode(), "hex_codec")

    def _deserialize_hex_string(self, digits: int, buf: bytearray, state: EOSAbiState):
        slice_ = buf[:digits]
        buf = buf[digits:]
        return codecs.encode(slice_, "hex_codec")

    def _serialize_bytes(self, state: EOSAbiState, buf: bytearray, data):
        new_buf = bytearray()
        if isinstance(data, (bytes, bytearray)):
            new_buf += data
        elif isinstance(data, list):
            new_buf.extend(map(int, data))
        elif isinstance(data, str):
            new_buf += codecs.decode(data.encode(), "hex_codec")
        else:
            raise ValueError("What is this data supposed to be?  %s" % data)
        self._serialize_varuint32(state, buf, len(new_buf))
        buf += new_buf

    def _deserialize_bytes(self, buf: bytearray, state: EOSAbiState):
        length = self._deserialize_varuint32(buf, state)
        slice_ = buf[:length]
        buf = buf[length:]
        return codecs.encode(slice_, "hex_codec")

    def _serialize_string(self, state: EOSAbiState, buf: bytearray, data: str):
        new_buf = bytearray(data.encode("utf-8"))
        self._serialize_varuint32(state, buf, len(new_buf))
        buf += new_buf

    def _deserialize_string(self, buf: bytearray, state: EOSAbiState):
        length = self._deserialize_varuint32(buf, state)
        slice_ = buf[:length]
        buf = buf[length:]
        return slice_.decode("utf-8")

    name_symbols = ".12345abcdefghijklmnopqrstuvwxyz"

    def _serialize_name(self, state: EOSAbiState, buf: bytearray, data: str):
        new_buf = bytearray(8)
        data += 13 * "."
        data = data[:13]
        bit = 63
        for i in range(len(data)):
            c = self.name_symbols.index(data[i])
            if bit < 5:
                c <<= 1
            for j in [4, 3, 2, 1, 0]:
                if bit >= 0:
                    new_buf[bit >> 3] |= ((c >> j) & 1) << (bit & 7)
                    bit -= 1

        buf += new_buf

    def _deserialize_name(self, buf: bytearray, state: EOSAbiState):
        slice_ = buf[:8]
        buf = buf[8:]
        result = ''
        bit = 63
        while bit >= 0:
            c = 0
            for i in range(5):
                if bit >= 0:
                    c <<= 1
                    c |= (slice_[bit >> 3] >> (bit & 7)) & 1
                    bit -= 1
            result += self.name_symbols[c]

        result = result.rstrip(".")
        return result

    def _serialize_time_point(self, state: EOSAbiState, buf: bytearray, data: str):
        timestamp = datetime.fromisoformat(data)
        timestamp = int(timestamp.timestamp() * 1000)
        self._serialize_packed("<Q", state, buf, timestamp)

    def _deserialize_time_point(self, buf: bytearray, state: EOSAbiState):
        timestamp = self._deserialize_packed("<Q", buf, state)
        timestamp = datetime.utcfromtimestamp(timestamp / 1000.0)
        timestamp = timestamp.isoformat()
        return timestamp

    def _serialize_time_point_sec(self, state: EOSAbiState, buf: bytearray, data: str):
        timestamp = datetime.fromisoformat(data)
        timestamp = timestamp.timestamp()
        self._serialize_packed("<L", state, buf, timestamp)

    def _deserialize_time_point_sec(self, buf: bytearray, state: EOSAbiState):
        timestamp = self._deserialize_packed("<L", buf, state)
        timestamp = datetime.utcfromtimestamp(timestamp)
        timestamp = timestamp.isoformat()
        return timestamp

    def _serialize_block_timestamp_type(self, state: EOSAbiState, buf: bytearray, data: str):
        timestamp = datetime.fromisoformat(data)
        # Number of half seconds since Jan 1, 2000 00:00:00 GMT
        timestamp = int((((timestamp.timestamp() - 946684800) * 2) + 1) / 2)
        self._serialize_packed("<L", state, buf, timestamp)

    def _deserialize_block_timestamp_type(self, buf: bytearray, state: EOSAbiState):
        timestamp = self._deserialize_packed("<L", buf, state)
        # Number of half seconds since Jan 1, 2000 00:00:00 GMT
        timestamp = datetime.utcfromtimestamp((timestamp * 2) + 946684800)
        timestamp = timestamp.isoformat()
        return timestamp

    symbol_re = re.compile(r'^([0-9]+),([A-Z]+)S')

    def _serialize_symbol_code(self, state: EOSAbiState, buf: bytearray, data: str):
        data = data[:8]
        buf += data.encode()
        buf += (8 - len(data)) * b'\x00'

    def _deserialize_symbol_code(self, buf: bytearray, state: EOSAbiState):
        slice_ = buf[:8]
        buf = buf[8:]
        slice_.rstrip(b'\x00')
        return slice_.decode()

    def _serialize_symbol(self, state: EOSAbiState, buf: bytearray, data: str):
        # precision,symbol_code
        match = self.symbol_re.match(data)
        if not match:
            raise ValueError("Invalid symbol: %s" % data)
        precision = match.group(1)
        symbol_code = match.group(2)
        buf += int(precision) & 0xFF
        self._serialize_symbol_code(state, buf, symbol_code)

    def _deserialize_symbol(self, buf: bytearray, state: EOSAbiState):
        precision = buf.pop(0)
        symbol_code = self._deserialize_symbol_code(buf, state)
        return "%s,%s" % (precision, symbol_code)

    asset_re = re.compile(r'^\s*(?P<amount>-?[0-9]+(?:\.(?P<decimals>[0-9]+))?)\s*(?P<symbol>[A-Z]+)\s*$', re.I)

    def _serialize_asset(self, state: EOSAbiState, buf: bytearray, data: str):
        match = self.asset_re.match(data)
        if not match:
            raise ValueError("Could not parse asset: %s" % data)

        decimals = match.group("decimals")
        if not decimals:
            decimals = ""
        precision = len(decimals)
        symbol_code = match.group("symbol")

        amount = match.group("amount")
        amount = amount.replace(".", "")
        amount = int(amount)
        if amount < 0:
            # We want just 1s complement (negated)
            amount &= ((1 << 64) - 1)
            amount -= 1
        self._serialize_packed("<Q", state, buf, int(amount))
        self._serialize_symbol(state, buf, "%s,%s" % (precision, symbol_code))

    def _deserialize_asset(self, buf: bytearray, state: EOSAbiState):
        amount = self._deserialize_packed("<Q", buf, state)
        if amount & (1 << 63):
            # 1s complement back to negative
            amount = 0 - (~amount & ((1 << 64) - 1))
        symbol = self._deserialize_symbol(buf, state)
        (precision, symbol_code) = symbol.split(",")
        amount = str(amount)
        length = len(amount)
        digits = length - precision
        amount = amount[:digits] + "." + amount[digits:]
        amount = amount.rstrip(".")
        return "%s %s" % (amount, symbol_code)

    public_key_data_size = 33
    private_key_data_size = 32
    signature_data_size = 65

    class KeyType(Enum):
        k1 = 0
        r1 = 1

    @staticmethod
    def _string_to_key(data: str, key_len: int, suffix: bytes):
        whole = base58.b58decode(data[:key_len + 4])
        h = RIPEMD160.new()
        h.update(whole)
        if suffix:
            h.update(suffix)
        digest = h.digest()
        if digest[:4] != whole[-4:]:
            raise ValueError("Checksum doesn't match")
        return whole

    def _serialize_public_key(self, state: EOSAbiState, buf: bytearray, data: str):
        if data.startswith("EOS"):
            key = self._string_to_key(data[3:], self.public_key_data_size, None)
            key_type = EOSAbiType.KeyType.k1
        elif data.startswith("PUB_K1_"):
            key = self._string_to_key(data[7:], self.public_key_data_size, b"K1")
            key_type = EOSAbiType.KeyType.k1
        elif data.startswith("PUB_R1_"):
            key = self._string_to_key(data[7:], self.public_key_data_size, b"R1")
            key_type = EOSAbiType.KeyType.r1
        else:
            raise ValueError("Unknown public key type")

        buf.append(EOSAbiType.KeyType(key_type).value)
        buf += key[:self.public_key_data_size]

    @staticmethod
    def _key_to_string(key: bytearray, key_len: int, suffix: bytes, prefix: str):
        if len(key) != key_len:
            raise ValueError("Key is not correct size")

        h = RIPEMD160.new()
        h.update(key)
        h.update(suffix)
        digest = h.digest()

        whole = bytearray(key)
        whole += digest

        return prefix + base58.b58encode(whole).decode()

    def _deserialize_public_key(self, buf: bytearray, state: EOSAbiState):
        key_type = EOSAbiType.KeyType(buf.pop(0))
        key = buf[:self.public_key_data_size]
        buf = buf[self.public_key_data_size:]

        if key_type == EOSAbiType.KeyType.k1:
            prefix = "PUB_K1_"
            suffix = b"K1"
        elif key_type == EOSAbiType.KeyType.r1:
            prefix = "PUB_R1_"
            suffix = b"R1"
        else:
            raise ValueError("Unknown public key type")

        return self._key_to_string(key, self.public_key_data_size, suffix, prefix)

    def _serialize_private_key(self, state: EOSAbiState, buf: bytearray, data: str):
        if data.startswith("PVT_R1_"):
            key = self._string_to_key(data[7:], self.private_key_data_size, b"R1")
            key_type = EOSAbiType.KeyType.r1
        else:
            raise ValueError("Unknown private key type")

        buf.append(EOSAbiType.KeyType(key_type).value)
        buf += key[:self.private_key_data_size]

    def _deserialize_private_key(self, buf: bytearray, state: EOSAbiState):
        key_type = EOSAbiType.KeyType(buf.pop(0))
        key = buf[:self.private_key_data_size]
        buf = buf[self.private_key_data_size:]

        if key_type == EOSAbiType.KeyType.r1:
            prefix = "PVT_R1_"
            suffix = b"R1"
        else:
            raise ValueError("Unknown private key type")

        return self._key_to_string(key, self.private_key_data_size, suffix, prefix)

    def _serialize_signature(self, state: EOSAbiState, buf: bytearray, data: str):
        if data.startswith("SIG_K1_"):
            key = self._string_to_key(data[7:], self.signature_data_size, b"K1")
            key_type = EOSAbiType.KeyType.k1
        elif data.startswith("SIG_R1_"):
            key = self._string_to_key(data[7:], self.signature_data_size, b"R1")
            key_type = EOSAbiType.KeyType.r1
        else:
            raise ValueError("Unknown signature type")

        buf.append(EOSAbiType.KeyType(key_type).value)
        buf += key[:self.signature_data_size]

    def _deserialize_signature(self, buf: bytearray, state: EOSAbiState):
        key_type = EOSAbiType.KeyType(buf.pop(0))
        key = buf[:self.signature_data_size]
        buf = buf[self.signature_data_size:]

        if key_type == EOSAbiType.KeyType.k1:
            prefix = "SIG_K1_"
            suffix = b"K1"
        elif key_type == EOSAbiType.KeyType.r1:
            prefix = "SIG_R1_"
            suffix = b"R1"
        else:
            raise ValueError("Unknown signature type")

        return self._key_to_string(key, self.signature_data_size, suffix, prefix)

    def _serialize_struct(self, state: EOSAbiState, buf: bytearray, data: dict):
        if self.base_type:
            self.base_type.serializer(buf, data)

        for field in self.fields:
            field_name = field.get("name", None)
            field_data = data.get(field_name, None)
            type_ = field.get("type", None)
            if not type_:
                raise KeyError("Improperly configured type for %s.%s" % (self.name, field_name))
            if field_data is not None:
                if state.skipped_binary_extensions:
                    raise KeyError("Unexpected %s.%s" % (self.name, field_name))
                new_state = EOSAbiState(state)
                new_state.allow_extensions = state.allow_extensions and (field == self.fields[-1])
                type_.serializer(new_state, buf, field_data)
            else:
                if state.allow_extensions and type_.extension_of is not None:
                    state.skipped_binary_extensions = True
                else:
                    raise KeyError("Missing %s.%s" % (self.name, field_name))

    def _deserialize_struct(self, buf: bytearray, state: EOSAbiState):
        result = {}
        if self.base_type:
            result.update(self.base_type.deserializer(buf, state))

        for field in self.fields:
            type_ = field.get("type", None)
            field_name = field.get("name", None)
            if type_ is None:
                raise KeyError("Improperly configured type for %s.%s" % (self.name, field_name))
            if state.allow_extensions and type_.extension_of is not None and len(buf) == 0:
                state.skipped_binary_extensions = True
            else:
                result[field_name] = type_.deserializer(buf, state)

        return result

    def _serialize_array(self, state: EOSAbiState, buf: bytearray, data: list):
        self._serialize_varuint32(state, buf, len(data))
        for item in data:
            self.array_of.serializer(state, buf, item)

    def _deserialize_array(self, buf: bytearray, state: EOSAbiState):
        length = self._deserialize_varuint32(buf, state)
        return [self.array_of.deserializer(buf, state) for i in range(length)]

    def _serialize_optional(self, state: EOSAbiState, buf: bytearray, data):
        self._serialize_packed("?", state, buf, (data is None))
        if data is not None:
            self.optional_of.serializer(state, buf, data)

    def _deserialize_optional(self, buf: bytearray, state: EOSAbiState):
        exists = self._deserialize_packed("?", buf, state)
        if not exists:
            return None
        return self.optional_of.deserializer(buf, state)

    def _serialize_extension(self, state: EOSAbiState, buf: bytearray, data):
        self.extension_of.serializer(state, buf, data)

    def _deserialize_extension(self, buf: bytearray, state: EOSAbiState):
        return self.extension_of.deserializer(buf, state)

    def _serialize_variant(self, state: EOSAbiState, buf: bytearray, data: list):
        if not isinstance(data, list) or len(data) != 2 or not isinstance(data[0], str):
            raise ValueError('Expected variant: ["type", value]')
        (field_name, value) = data

        field_names = [item.get("name", None) for item in self.fields]
        try:
            index = field_names.index(field_name)
            type_ = self.fields[index].get("type", None)
            if not type_:
                raise ValueError
        except ValueError as e:
            raise ValueError("Type %s is not valid for variant" % field_name)

        self._serialize_varuint32(state, buf, index)
        type_.serializer(state, buf, value)

    def _deserialize_variant(self, buf: bytearray, state: EOSAbiState):
        index = self._deserialize_varuint32(buf, state)
        if index >= len(self.fields):
            raise ValueError("type index %s is not valid for variant" % index)
        field = self.fields[index]
        field_name = field.get("name", None)
        type_ = field.get("type", None)
        return [field_name, type_.deserializer(buf, state)]


class EOSAbi(object):
    @staticmethod
    def lookup(contract: str):
        with abi_map_lock:
            abi = abi_map.get(contract, None)
            if not abi:
                abi = EOSAbi(contract)
                abi_map[contract] = abi
            return abi

    def __init__(self, contract):
        try:
            from HavokMud.startup import server_instance
            server = server_instance

            # The contract is also the name of the account that holds the contract
            response = server.chain_api.call("get_abi", account_name=contract, openapi_validate=False)
        except Exception as e:
            logger.exception("Contract: %s" % contract)
            raise EOSAbiError("Could not pull ABI for contract %s: %s" % (contract, e))

        with open("/tmp/abi-%s.json" % contract, "w") as f:
            json.dump(response, f, indent=2, sort_keys=True)

        self.abi = response.get("abi", {})

        # Now for the fun...  Time to parse out the types and structures and variants
        self.types = None
        self._parse_types()

        # Let's flatten the actions for easier use
        actions = {item.get("name", None): item
                   for item in self.abi.get("actions", [])
                   if isinstance(item, dict)}
        self.abi['actions'] = actions

    def get(self, key, default):
        return self.abi.get(key, default)

    def _parse_types(self):
        base_types = EOSAbiBaseTypes()
        types = dict(base_types.types)

        # Type aliases
        for item in self.abi.get('types', []):
            type_ = item.get('new_type_name', None)
            if not type_:
                continue
            types[type_] = EOSAbiType(type_, alias=item.get('type', None))

        # Structs
        for item in self.abi.get('structs', []):
            name = item.get('name', None)
            if not name:
                continue
            base_type = item.get('base', None)
            fields = item.get("fields", [])
            for field in fields:
                field['type_name'] = field.get('type', None)
            types[name] = EOSAbiType(name, base_name=base_type, fields=fields)

        # Variants
        for item in self.abi.get("variants", []):
            (name, types) = item
            fields = [{"name": type_, "type_name": type_} for type_ in types]
            types[name] = EOSAbiType(name, variant=True, fields=fields)

        # Now to extract arrays, etc.
        check_types = dict(types)
        while check_types:
            new_types = {}
            for (name, item) in check_types.items():
                # logger.debug("name: %s, item: %s" % (name, item.__dict__))
                if item.base_name:
                    item.base_type = EOSAbiType.get(types, new_types, item.base_name)
                if hasattr(item, "fields") and isinstance(item.fields, list):
                    for field in item.fields:
                        field['type'] = EOSAbiType.get(types, new_types, field.get('type_name', None))

            types.update(check_types)
            check_types = new_types

        self.types = types

    def serialize(self, type_name: str, data):
        state = EOSAbiState()
        buf = bytearray()
        type_ = self.types.get(type_name, None)
        if not type_:
            raise KeyError("Type %s not found" % type_name)
        type_.serializer(state, buf, data)
        return codecs.encode(buf, "hex_codec").decode()

    def deserialize(self, type_name: str, data: str):
        state = EOSAbiState()
        type_ = self.types.get(type_name, None)
        if not type_:
            raise KeyError("Type %s not found" % type_name)
        buf = bytearray(codecs.decode(data.encode(), "hex_codec"))
        return type_.deserializer(buf, state)


class EOSAbiBaseTypes(object):
    base_types = {
        'bool': {"pack_": "?"},
        'uint8': {"pack_": "B"},
        'int8': {"pack_": "b"},
        'uint16': {"pack_": '<H'},
        'int16': {"pack_": '<h'},
        'uint32': {"pack_": '<L'},
        'int32': {"pack_": '<l'},
        'uint64': {"pack_": "<Q"},
        'int64': {"pack_": "<q"},
        'varuint32': {},
        'varint32': {},
        'uint128': {},
        'int128': {},
        'float32': {"pack_": "<f"},
        'float64': {"pack_": "<d"},
        'float128': {"hex_digits": 16},
        'bytes': {},
        'string': {},
        'name': {},
        'time_point': {},
        'time_point_sec': {},
        'block_timestamp_type': {},
        'symbol_code': {},
        'symbol': {},
        'asset': {},
        'checksum160': {"hex_digits": 20},
        'checksum256': {"hex_digits": 32},
        'checksum512': {"hex_digits": 64},
        'public_key': {},
        'private_key': {},
        'signature': {},
        'extended_asset': {"fields": [
            {"name": 'quantity', 'type_name': 'asset'},
            {"name": "contract", 'type_name': 'name'},
        ]},
    }
    types = {}

    def __init__(self):
        self.types = {name: EOSAbiType(name, **kwargs)
                      for (name, kwargs) in self.base_types.items()}
