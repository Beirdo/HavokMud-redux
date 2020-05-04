import hashlib
import logging
import random
import re
import time
from functools import wraps

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


def double_wrap(func):
    '''
    a decorator decroator allowing the decorator to be used as:
    @decorator(with, args, and=kwargs)
    or
    @decorator
    '''

    @wraps(func)
    def new_decorator(*args, **kwargs):
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            # actual decorated function
            return func(args[0])
        else:
            # decorator with arguments
            return lambda real_func: func(real_func, *args, **kwargs)

    return new_decorator


@double_wrap
def log_call(func, censor=False):
    def _censor(censor_, key, value):
        if key in censor_:
            return "*censored*"
        return value

    def wrapper(*args, **kwargs):
        log_args = ["%s" % item for item in args] + \
                   ["%s=%s" % (key, value) for (key, value) in kwargs.items()]
        func_name = ".".join([func.__module__, func.__qualname__])
        if censor:
            censors = censor
            if not isinstance(censors, (list, tuple, set)):
                censors = {censors}

            censors = set(censors)

            arg_censor = set()
            kwarg_censor = set()

            if "all_args" in censors:
                # noinspection PyTypeChecker
                censors.remove("all_args")
                arg_censor |= set(range(len(args)))

            if "all_kwargs" in censors:
                # noinspection PyTypeChecker
                censors.remove("all_kwargs")
                kwarg_censor |= set(kwargs.keys())

            exclusions = set(filter(lambda x: str(x).startswith("!"), censors))
            censors -= exclusions

            exclusions = set(map(lambda x: str(x)[1:], exclusions))
            arg_exclusions = set(map(int, filter(str.isnumeric, exclusions)))
            kwarg_exclusions = set(filter(lambda x: not x.isnumeric(), exclusions))

            arg_censor -= arg_exclusions
            kwarg_censor -= kwarg_exclusions

            arg_censor |= set(filter(lambda x: str(x).isnumeric(), censors))
            kwarg_censor |= (censors - arg_censor)

            censored_args = ["%s" % _censor(arg_censor, index, item) for (index, item) in enumerate(args)] + \
                            ["%s=%s" % (key, _censor(kwargs_censor, key, value)) for (key, value) in kwargs.items()]
            func_signature = "%s(%s)" % (func_name, ", ".join(censored_args))
        else:
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
