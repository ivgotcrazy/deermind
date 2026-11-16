"""认证安全配置；本机HTTP例外必须显式启用且仅限回环域名。"""

import os
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network, ip_network
from urllib.parse import urlsplit


@dataclass(frozen=True)
class AuthConfig:
    origins: frozenset[str]
    local_http: bool
    trusted_proxies: tuple[IPv4Network | IPv6Network, ...] = ()

    def __post_init__(self) -> None:
        if not self.origins:
            raise ValueError("Authentication requires explicit origins")
        for origin in self.origins:
            url = urlsplit(origin)
            scheme = "http" if self.local_http else "https"
            if (
                url.scheme != scheme
                or not url.hostname
                or url.username
                or url.password
                or url.path
                or url.query
                or url.fragment
                or (self.local_http and url.hostname not in {"localhost", "127.0.0.1"})
            ):
                raise ValueError("Invalid authentication origin")

    @property
    def cookie_name(self) -> str:
        return "dm_session_local" if self.local_http else "__Host-dm_session"

    @classmethod
    def from_environment(cls) -> "AuthConfig":
        mode = os.environ.get("M1_AUTH_LOCAL_HTTP", "false")
        if mode not in {"true", "false"}:
            raise ValueError("M1_AUTH_LOCAL_HTTP must be true or false")
        return cls(
            frozenset(filter(None, os.environ["M1_AUTH_ORIGINS"].split(","))),
            mode == "true",
            tuple(
                ip_network(value)
                for value in os.environ.get("M1_AUTH_TRUSTED_PROXIES", "").split(",")
                if value
            ),
        )
