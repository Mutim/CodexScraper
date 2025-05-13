import os
import json
from typing import Optional
from dataclasses import dataclass, field

from supabase import create_client


__all__ = (
    'Info',
    'get_supabase_client',
    'CONFIG_FILE',
    'COLOR_CODES',
    'load_config',
    'update_config'

)

# import config
CONFIG_FILE = 'config.json'

COLOR_CODES = {
    "RED": "\033[0;31m",
    "GREEN": "\033[0;32m",
    "YELLOW": "\033[0;33m",
    "BLUE": "\033[0;34m",
    "MAGENTA": "\033[0;35m",
    "CYAN": "\033[0;36m",
    "WHITE": "\033[0;37m",
    "RESET": "\033[0m"
}


# TODO: Make this a dataclass  -- DONE
@dataclass
class InfoManager:
    """Configuration manager"""
    _supabase_url: Optional[str] = field(default=None, init=False)
    _supabase_key: Optional[str] = field(default=None, init=False)
    _ashes_auth: Optional[str] = field(default=None, init=False)
    _ashes_key: Optional[str] = field(default=None, init=False)
    _user: Optional[str] = field(default=None, init=False)
    _password: Optional[str] = field(default=None, init=False)
    _host: Optional[str] = field(default=None, init=False)
    _port: str = field(default="5432", init=False)  # Default port

    def refresh(self):
        """Reload environment variables"""
        self._supabase_url = os.getenv("SUPABASE_URL")
        self._supabase_key = os.getenv("SUPABASE_KEY")
        self._ashes_auth = os.getenv("ASHES_AUTH")
        self._ashes_key = os.getenv("ASHES_KEY")
        self._user = os.getenv("USER")
        self._password = os.getenv("PASSWORD")
        self._host = os.getenv("HOST")
        self._port = os.getenv("PORT", self._port)  # Use default if not set

    # Supabase credentials -
    # Found at https://supabase.com/dashboard/project/{your-database-url}/settings/api
    @property
    def supabase_url(self) -> str:
        if self._supabase_url is None:
            self.refresh()
        return self._supabase_url

    @property
    def supabase_key(self) -> str:
        if self._supabase_key is None:
            self.refresh()
        return self._supabase_key

    # Ashes information -
    # This info is not needed, and can safely be left blank in your .env file.
    # However, it is needed when pulling user specific information from the site, such as custom markers.
    @property
    def ashes_auth(self) -> Optional[str]:
        if self._ashes_auth is None:
            self.refresh()
        return self._ashes_auth

    @property
    def ashes_key(self) -> Optional[str]:
        if self._ashes_key is None:
            self.refresh()
        return self._ashes_key

    # Database Information -
    # Found at https://supabase.com/dashboard/project/{your-database-url}/editor?
    @property
    def user(self) -> str:
        if self._user is None:
            self.refresh()
        return self._user

    @property
    def password(self) -> str:
        if self._password is None:
            self.refresh()
        return self._password

    @property
    def host(self) -> str:
        if self._host is None:
            self.refresh()
        return self._host

    @property
    def port(self) -> str:
        if self._port is None:
            self.refresh()
        return self._port

    def validate(self):
        required = [
            ("SUPABASE_URL", self.supabase_url),
            ("SUPABASE_KEY", self.supabase_key),
            ("HOST", self.host),
            ("PORT", self.port),
            ("USER", self.user),
            ("PASSWORD", self.password)
        ]
        missing = [name for name, value in required if not value]
        if missing:
            raise ValueError(f"Missing required config: {', '.join(missing)}")


# Instance teh dataclass
Info = InfoManager()


def get_supabase_client():
    return create_client(Info.supabase_url, Info.supabase_key)


def load_config(config_file: str):
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)

        # Post-process to replace placeholders with color codes
        for key, value in config_data["TEXTS"].items():
            if isinstance(value, str):
                for color, code in COLOR_CODES.items():
                    value = value.replace(f"[{color}]", code)
                config_data["TEXTS"][key] = value

        return config_data


def update_config(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
