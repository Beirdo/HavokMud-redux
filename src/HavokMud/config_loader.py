import json
import logging
import os
import re

logger = logging.getLogger(__name__)

configDir = os.path.expanduser("~/.havokmud")


def load_config_file(filename):
    config_file = os.path.join(configDir, filename)
    try:
        with open(config_file) as f:
            config = json.load(f)
    except Exception:
        logger.critical("Could not load configuration file %s" % config_file)
        config = {}

    return config


def load_raw_file(filename):
    raw_file = os.path.join(configDir, filename)
    try:
        with open(raw_file) as f:
            data = f.read()
    except Exception:
        logger.critical("Could not load raw file %s" % raw_file)
        data = None

    return data


passwordFileRe = re.compile(r'(?P<account>.*?)\.password', re.I)


def load_all_wallet_passwords(passwords):
    from HavokMud.startup import server_instance
    encryption = server_instance.encryption

    logger.info("Loading system wallet passwords")
    to_delete = set()
    for (root, dirs, files) in os.walk(os.path.join(configDir, "passwords")):
        for file_ in files:
            filename = os.path.join(root, file_)
            match = passwordFileRe.match(file_)
            if not match:
                continue

            account = match.group("account")
            logger.info("Loading wallet password for account %s" % account)

            with open(filename) as f:
                new_password = f.read()
            to_delete.add(filename)

            existing_password = passwords.get(account, None)
            if existing_password:
                logger.info("Decrypting existing wallet password for account %s" % account)
                existing_password = encryption.decrypt_string(existing_password)
                if new_password == existing_password:
                    logger.info("Passwords match, skipping")
                    continue

            logger.info("Encrypting wallet password for account %s" % account)
            passwords[account] = encryption.encrypt_string(new_password)

    for file_ in to_delete:
        logger.info("Deleting %s" % file_)
        os.unlink(file_)

    return passwords
