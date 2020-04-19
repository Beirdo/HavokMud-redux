import base64
import logging

import boto3
from Crypto import Random
from Crypto.Cipher import PKCS1_OAEP, AES
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

logger = logging.getLogger(__name__)


class EncryptionEngine(object):
    def __init__(self, config):
        self.config = config

        self.region = self.config.get("mud", {}).get("region", "us-east-1")
        mudname = self.config.get("mud", {}).get("name", "ConfigureMe")

        encryption_config = self.config.get("encryption", {})
        self.endpoint = encryption_config.get("endpoint", None)
        self.use_ssl = encryption_config.get("useSsl", True)

        logger.info("Endpoint: %s" % self.endpoint)
        self.session = boto3.session.Session(region_name=self.region)
        self.smclient = self.session.client('secretsmanager', endpoint_url=self.endpoint, use_ssl=self.use_ssl)

        logger.info("Attempting to pull encryption key from SecretsManager")
        privatekey = None
        while privatekey is None:
            try:
                response = self.smclient.get_secret_value(SecretId=mudname + "-core")
            except Exception as e:
                logger.exception("Ouch.  No bueno!")
                response = {}

            pemkey = response.get('SecretString', None)
            binkey = response.get('SecretBinary', None)
            if pemkey:
                logger.info("Received key in string format")
                privatekey = RSA.import_key(pemkey)
            elif binkey:
                logger.info("Received key in binary format")
                binkey = base64.b64decode(binkey)
                privatekey = RSA.import_key(binkey)
            else:
                logger.info("response: %s" % response)
                logger.info("Creating new 2048 bit RSA key pair")
                privatekey = RSA.generate(2048, Random.new().read)
                logger.info("Sending new encryption key to SecretsManager")
                params = {
                    "Name": mudname + "-core",
                    "SecretString": privatekey.export_key("PEM").decode("utf-8"),
                }
                try:
                    self.smclient.create_secret(**params)
                except self.smclient.exceptions.ResourceExistsException:
                    # Hmm, seems it told us a lie, it's already set, so try again
                    logger.info("Retrying, seems it already IS there")
                    privatekey = None

        self.public_key = privatekey.publickey()
        self._private_key = privatekey

    def encrypt(self, data):
        session_key = get_random_bytes(16)

        # Encrypt session key with the public RSA key
        cipher_rsa = PKCS1_OAEP.new(self.public_key)
        enc_session_key = cipher_rsa.encrypt(session_key)

        # Encrypt the data with the AES session key
        cipher_aes = AES.new(session_key, AES.MODE_EAX)
        (ciphertext, tag) = cipher_aes.encrypt_and_digest(data)

        out_message = [enc_session_key, cipher_aes.nonce, tag, ciphertext]
        out_message = "$".join([base64.b64encode(item).decode("utf-8") for item in out_message])
        return out_message

    def decrypt(self, data):
        in_message = [base64.b64decode(item.encode("utf-8")) for item in data.split("$")]
        if len(in_message) != 4:
            raise ValueError("Improperly formed encrypted message")
        (enc_session_key, nonce, tag, ciphertext) = in_message

        # Decrypt the session key with the private RSA key
        cipher_rsa = PKCS1_OAEP.new(self._private_key)
        session_key = cipher_rsa.decrypt(enc_session_key)

        # Decrypt the data with the AES session key
        cipher_aes = AES.new(session_key, AES.MODE_EAX, nonce)
        data = cipher_aes.decrypt_and_verify(ciphertext, tag)
        return data

    def encrypt_string(self, data, encoding="utf-8"):
        return self.encrypt(data.encode(encoding))

    def decrypt_string(self, data, encoding="utf-8"):
        return self.decrypt(data).decode(encoding)
