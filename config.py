import os
import shutil
import logging
import typing
from dataclasses import fields, MISSING, is_dataclass
from typing import Type, Any

from yaml import safe_load


class ConfigClass:
    @staticmethod
    def parse(data: Any, type_hint):
        origin = typing.get_origin(type_hint)
        if origin is list:
            result = list()
            for value in data:
                result.append(ConfigClass.parse(value, typing.get_args(type_hint)[0]))
        elif origin is dict:
            result = dict()
            for key, value in data.items():
                result[key] = ConfigClass.parse(value, typing.get_args(type_hint)[1])
        elif origin is None and is_dataclass(type_hint):
            if issubclass(type_hint, ConfigClass):
                result = type_hint.from_dict(data)
            else:
                raise TypeError(f"Nested dataclass {type_hint}) is not subclass of ConfigClass")
        else:
            result = data
        return result

    @classmethod
    def from_dict(cls, data: dict):
        kwargs = {}
        hints = typing.get_type_hints(cls)
        for f in fields(cls):
            if f.name not in data:
                if f.default != MISSING or f.default_factory != MISSING:
                    continue
                raise ValueError(f"{cls.__name__}.{f.name} is not configured!")
            kwargs[f.name] = ConfigClass.parse(data[f.name], hints[f.name])
        return cls(**kwargs)

    @classmethod
    def from_file(cls, filepath: str, config_namespace: str = ""):
        with open(filepath) as f:
            data = safe_load(f)
        if data is None:
            raise ValueError("Configuration file seems to be empty")
        if config_namespace:
            data = data.get(config_namespace, {})
        return cls.from_dict(data)


def load_config(main_config: Type[ConfigClass],
                config_namespace: str = "",
                config_path: str = "config.yaml",
                example_config_path: str = "config-example.yaml"):
    if not os.path.exists(config_path):
        logging.warning(f"Unable to locate app config ({config_path})!")
        if not os.path.exists(example_config_path):
            logging.critical(f"Unable to locate example config ({example_config_path})")
            exit(1)
        else:
            shutil.copy2(example_config_path, config_path)
            logging.warning(f"Actual app config (%s) created from example (%s), don't forget to update it!",
                            config_path, example_config_path)
    return main_config.from_file(config_path, config_namespace)
