import logging
import logging.config
import os

LOGDIR = "/var/log/havokmud"


class AccountLogMessage(object):
    def __init__(self, account, message, _global=False):
        self.ip = account.ip_address
        self.email = account.email
        self.message = message
        self._global = _global

    def __str__(self):
        return self.message


class PlayerLogMessage(AccountLogMessage):
    def __init__(self, player, message, _global=False, account=False):
        AccountLogMessage.__init__(self, player.account, message, _global)
        self.player = player.name
        self._account = account


class LogFilter(logging.Filter):
    def __init__(self, logType=None):
        logging.Filter.__init__(self)
        if logType is None:
            logType = "global"
        self.logType = logType

    def filter(self, record):
        record.logType = self.logType
        message = record.msg
        logType = self.logType

        if isinstance(message, str):
            if logType in ["global", "all"]:
                record.ip = "-"
                record.email = "-"
                record.player = "-"
                return True

        if isinstance(message, AccountLogMessage):
            # noinspection PyProtectedMember
            if logType in ["account", "all"] or (logType == "global" and message._global):
                record.ip = message.ip
                record.email = message.email
                record.player = "-"
                return True

        if isinstance(message, PlayerLogMessage):
            # noinspection PyProtectedMember
            if logType in ["player", "all"] or (logType == 'global' and message._global) \
                    or ("logType" == "account" and message._account):
                record.ip = message.ip
                record.email = message.email
                record.player = message.player
                return True

        return False


class AccountLogHandler(logging.Handler):
    files = {}

    def emit(self, record):
        msg = self.format(record)
        fp = self.files.get(record.email, None)
        if not fp:
            filename = os.path.join(LOGDIR, "account-%s.log" % record.email)
            fp = open(filename, "a")
            self.files[record.email] = fp
        fp.write(msg + "\n")
        fp.flush()

    def closeEmail(self, email):
        fp = self.files.pop(email, None)
        if fp:
            fp.close()


class PlayerLogHandler(logging.Handler):
    files = {}

    def emit(self, record):
        msg = self.format(record)
        fp = self.files.get(record.player, None)
        if not fp:
            filename = os.path.join(LOGDIR, "player-%s.log" % record.player)
            fp = open(filename, "a")
            self.files[record.player] = fp
        fp.write(msg + "\n")
        fp.flush()

    def closePlayer(self, player):
        fp = self.files.pop(player, None)
        if fp:
            fp.close()


def logging_setup(logLevel, console=True):
    logConfig = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "allFilter": {
                "()": LogFilter,
                "logType": "all",
            },
            "globalFilter": {
                "()": LogFilter,
                "logType": "global",
            },
            "accountFilter": {
                "()": LogFilter,
                "logType": "account",
            },
            "playerFilter": {
                "()": LogFilter,
                "logType": "player",
            }
        },
        "handlers": {
            'console': {
                'class': 'logging.StreamHandler',
                'filters': ['allFilter'],
                'level': logLevel,
                'formatter': 'console',
            },
            'global': {
                'class': 'logging.FileHandler',
                'filters': ['globalFilter'],
                'level': logLevel,
                'formatter': 'default',
                'filename': os.path.join(LOGDIR, 'global.log'),
                'mode': "a",
                'encoding': 'utf-8',
            },
            'account': {
                'class': 'HavokMud.logging_support.AccountLogHandler',
                'filters': ['accountFilter'],
                'level': logging.DEBUG,
                'formatter': 'default',
            },
            'player': {
                'class': 'HavokMud.logging_support.PlayerLogHandler',
                'filters': ['playerFilter'],
                'level': logging.DEBUG,
                'formatter': 'default',
            }
        },
        "formatters": {
            "default": {
                "format": '%(asctime)s %(levelname)s [PID %(process)d] (%(name)s:%(lineno)d) %(ip)s %(email)s '
                          '%(player)s %(message)s',
            },
            "console": {
                "format": '%(asctime)s %(levelname)s (%(name)s:%(lineno)d) %(ip)s %(email)s %(player)s %(message)s'
            }

        },
        "root": {
            'handlers': ['global', 'account', 'player'],
            'level': logging.DEBUG,
        }
    }

    if console:
        logConfig["root"]["handlers"].append("console")

    os.makedirs(LOGDIR, 0o1777, exist_ok=True)

    logging.config.dictConfig(logConfig)


def logging_additional_setup(logLevelConfig):
    for (module, levelname) in logLevelConfig.items():
        logging.getLogger(module).setLevel(getattr(logging, levelname, "DEBUG"))
