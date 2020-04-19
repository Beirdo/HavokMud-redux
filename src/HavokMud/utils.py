import hashlib
import logging
import random
import re
import time

emailRe = re.compile(r'^([a-z0-9_\-.+]+)@([a-z0-9_\-.]+)\.([a-z]{2,20})$', re.I)

logger = logging.getLogger(__name__)


def validate_email(email):
    return emailRe.match(email)


def validate_yes_no(tokens):
    if not tokens:
        return None

    answer = tokens[0].lower()[:1]
    if answer != 'y' and answer != 'n':
        return None

    return answer == 'y'


def validate_password(tokens, match=None):
    if not tokens:
        return None

    password = tokens[0]
    if len(password) < 8:
        return None

    password = hashlib.sha512(password.encode("utf-8")).hexdigest()
    if not match:
        return password

    return password == match


def validate_pc_name(name):
    # TODO: implement blacklist
    return True


def validate_sex(tokens):
    if not tokens:
        return None

    answer = tokens[0].lower()[:1]
    if answer in ['m', 'f', 'n']:
        return answer

    return None


dice_re = re.compile(r'[dk]')


def roll_dice(dice):
    # Format:  like 2d6k1+1d4+8
    orig_dice = str(dice)
    dice = dice.split("+")
    rolls = []
    for die in dice:
        parts = dice_re.split(die)
        if len(parts) == 1:
            roll = [parts[0]]
        else:
            if len(parts) == 2:
                (count, size) = parts
                keep = count
            else:
                (count, size, keep) = parts
            roll = [random.randrange(size) + 1 for i in range(count)]
            while keep < len(roll):
                roll.remove(min(roll))

        item = {
            "description": die,
            "roll": roll,
        }
        rolls.append(item)

    response = {
        "details": rolls,
        "total": sum([roll for item in rolls for roll in item.get("roll", [])]),
    }

    text = ["%s" % item.get("roll", []) for item in rolls]
    response["text"] = "Roll: %s = %s: %s" % (orig_dice, response['total'], "+".join(text))
    return response


def log_call(func):
    def wrapper(*args, **kwargs):
        log_args = ["%s" % item for item in args] + \
                   ["%s=%s" % (key, value) for (key, value) in kwargs.items()]
        func_name = ".".join([func.__module__, func.__qualname__])
        func_signature = "%s(%s)" % (func_name, ", ".join(log_args))
        logger.info("Entering %s" % func_signature)
        start_time = time.time()
        ret_val = func(*args, **kwargs)
        end_time = time.time()
        logger.info("Exiting %s" % func_signature)
        duration = end_time - start_time
        logger.info("Duration: %.6fs" % duration)
        return ret_val

    return wrapper
