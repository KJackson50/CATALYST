import os
import yaml
from dotenv import load_dotenv

load_dotenv()

def env_bool(key: str, default: bool=False) -> bool:
    v = os.getenv(key, str(default)).strip().lower()
    return v in ("1", "true", "yes", "on")

class Settings:
    def __init__(self, settings_path: str = "settings.yaml") -> None:
        self.dnac_url = os.getenv("DNAC_URL")
        self.username = os.getenv("DNAC_USERNAME")
        self.password = os.getenv("DNAC_PASSWORD")
        self.verify_ssl = env_bool("DNAC_VERIFY_SSL", False)
        self.timeout = int(os.getenv("DNAC_TIMEOUT", "30"))
        self.http_proxy = os.getenv("HTTP_PROXY")
        self.https_proxy = os.getenv("HTTPS_PROXY")
        self.no_proxy = os.getenv("NO_PROXY")

        with open(settings_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self.global_cfg = data.get("global", {})
        self.sites = data.get("sites", {})

    def proxies(self):
        proxies = {}
        if self.http_proxy:
            proxies["http"] = self.http_proxy
        if self.https_proxy:
            proxies["https"] = self.https_proxy
        return proxies if proxies else None