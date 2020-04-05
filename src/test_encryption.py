#! /usr/bin/env python3
import json
import logging
import time

from HavokMud.encryption_helper import EncryptionEngine

logger = logging.getLogger(__name__)

format = '%(asctime)s %(levelname)s [PID %(process)d] (%(name)s:%(lineno)d) %(message)s'
logging.basicConfig(level=logging.INFO, format=format)

with open("/home/havokmud/.havokmud/config.json", "r") as f:
    config = json.load(f)

pre_create = time.time()
ee = EncryptionEngine(config)

message = "Hello there!"
pre_encrypt = time.time()
encrypted = ee.encrypt_string(message)
pre_decrypt = time.time()
decrypted = ee.decrypt_string(encrypted)
post_decrypt = time.time()

assert(message == decrypted)
logger.info("Initialization: %ss, Encryption: %ss, Decryption: %ss" %
            (pre_encrypt - pre_create, pre_decrypt - pre_encrypt, post_decrypt - pre_encrypt))
