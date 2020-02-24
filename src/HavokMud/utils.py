import hashlib
import re

emailRe = re.compile(r'^([a-z0-9_\-.+]+)@([a-z0-9_\-.]+)\.([a-z]{2,5})$', re.I)


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