from dataclasses import dataclass
from typing import overload
import logging

from config import ConfigClass, load_config


@dataclass
class LanguageConfig (ConfigClass):
    code: str
    phrases: dict[str, str]


@dataclass
class I18NConfig (ConfigClass):
    langs: list[LanguageConfig]

    def __len__(self):
        return len(self.langs)

    def __getitem__(self, key) -> LanguageConfig:
        for lang in self.langs:
            if lang.code == key:
                return lang
        raise KeyError(f"Language '{key}' not found!")


class I18N:
    def __init__(self, lang_code: str = "en", file: str = "i18n.yaml"):
        self._config = load_config(I18NConfig, config_path=file)
        self._phrases: dict[str, str] = self._config[lang_code].phrases
        self._fallback: dict[str, str] = {}

    @overload
    def reg_t(self, pair: tuple[str, str]):
        self._fallback[pair[0]] = pair[1]

    @overload
    def reg_t(self, dictionary: dict[str, str]):
        self._fallback.update(dictionary)

    def reg_t(self, value):
        pass

    def t(self, key, *args, **kwargs):
        phrase = self._phrases.get(key)
        if not phrase:
            logging.warning(f"No phrase '{key}' in loaded language, trying to use fallback dict")
            phrase = self._fallback.get(key)
            if not phrase:
                logging.error(f"No phrase '{key}' in fallback dict, returning the key")
                return key
        return phrase.format(*args, **kwargs)

