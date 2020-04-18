import logging

from HavokMud.database_object import DatabaseObject

logger = logging.getLogger(__name__)


class Settings(DatabaseObject):
    __fixed_fields__ = ["server"]
    __database__ = None

    def __init__(self, dbs, key, value=None):
        DatabaseObject.__init__(self)
        self.dbs = dbs
        self.__database__ = self.dbs.settings_db

        self.key = key
        self.value = value

    @staticmethod
    def lookup_by_key(server, key):
        # Look this up in DynamoDB
        item = Settings(server.dbs, key)

        # if not in dynamo: will return with empty value field
        item.load_from_db(key=key)

        return item

    @staticmethod
    def get_all_settings(dbs):
        settings = [Settings(dbs, key=item.get("key", None), value=item.get("value", None))
                    for item in dbs.settings_db.get_all()]
        return {item.key: item for item in settings}

    @staticmethod
    def get_updated_config(dbs, config):
        settings = Settings.get_all_settings(dbs)
        if settings:
            settings["mud:bootstrapped"] = True
        db_settings = set(settings.keys())
        config_settings = Settings._config_to_settings(dbs, config)
        config_settings.update(settings)
        new_settings = set(config_settings.keys())

        added_settings = new_settings - db_settings
        for setting in added_settings:
            config_settings[setting].save_to_db()

        new_config = Settings._settings_to_config(config_settings)
        return new_config

    @staticmethod
    def _config_to_settings(server, config: dict, prefix: list = None) -> dict:
        if not prefix:
            prefix = []
        out_map = {}
        for (key, value) in config.items():
            new_prefix = list(prefix)
            new_prefix.append(key)

            if isinstance(value, dict):
                out_map.update(Settings._config_to_settings(server, value, new_prefix))
            else:
                out_key = ":".join(new_prefix)
                out_map[out_key] = Settings(server, out_key, value)
        return out_map

    @staticmethod
    def _settings_to_config(settings: dict) -> dict:
        out_config = {}
        for (key, item) in settings.items():
            parts = key.split(":")
            value = item.value
            out_item = value
            for part in reversed(parts):
                out_item = {part: out_item}

            config_dict = out_config
            for part in parts:
                value = out_item.get(part, None)
                if not isinstance(value, dict):
                    config_dict[part] = value
                else:
                    out_item = value
                    if part not in config_dict:
                        config_dict[part] = {}
                    config_dict = config_dict[part]

        return out_config
