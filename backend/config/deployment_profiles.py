"""Fail-closed server deployment profile contract; independent of network-proxy implementation."""
import ipaddress
import re
from urllib.parse import urlsplit

class ProfileError(ValueError):
    pass

LOOPBACK = {"localhost", "127.0.0.1", "::1"}
DEV_HOSTS = LOOPBACK | {"api", "testserver"}
HOST = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.-]{0,251}[a-zA-Z0-9]$")


def _required(cond, message):
    if not cond:
        raise ProfileError("Unsafe deployment profile: " + message)


def _private_address(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    return ip.version == 4 and ip.is_private and not (ip.is_loopback or ip.is_link_local or
                                                     ip.is_multicast or ip.is_reserved or ip.is_unspecified)


def _internal_host(value):
    if _private_address(value):
        return True
    return bool(HOST.fullmatch(value) and value.lower().endswith((".lan", ".local", ".internal")))


def configuration(environ):
    """Validate **at Django startup**. The host-side CLI validates certificate files."""
    profile = environ.get("AI_COMPASS_PROFILE", "development").lower()
    _required(profile in ("development", "lan"), "profile must be development or lan")
    hosts = [x.strip().lower() for x in
             environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,api").split(",") if x.strip()]
    _required(hosts and len(set(hosts)) == len(hosts), "explicit unique ALLOWED_HOSTS required")
    _required("*" not in hosts and all("*" not in x and "/" not in x for x in hosts),
              "wildcard and CIDR hosts forbidden")
    if profile == "development":
        _required(set(hosts) <= DEV_HOSTS, "development hostnames must be loopback/internal api")
        _required(environ.get("AI_COMPASS_LAN_BIND", "") in ("", "127.0.0.1"),
                  "development cannot bind on LAN")
        _required(not environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", ""),
                  "development must not trust remote origins")
        _required(environ.get("AI_COMPASS_TLS_PROXY", "") != "1",
                  "do not silently enable proxy trust for HTTP development")
        return {"profile": profile, "allowed_hosts": hosts, "csrf_origins": [],
                "secure": False, "proxy_header": None}
    bind = environ.get("AI_COMPASS_LAN_BIND", "")
    _required(_private_address(bind), "LAN bind must be an explicit private non-loopback IPv4")
    _required(bind in hosts, "LAN bind must appear in allowed hosts")
    _required(all(h in DEV_HOSTS or _internal_host(h) for h in hosts),
              "LAN hosts must be private IPv4 or internal DNS")
    _required(environ.get("AI_COMPASS_TLS_PROXY") == "1",
              "LAN requires a TLS-terminating trusted proxy")
    for secret in ("DJANGO_SECRET_KEY", "DB_PASSWORD"):
        value = environ.get(secret, "")
        _required(len(value) >= 32 and not value.startswith("REPLACE_WITH_"),
                  "LAN requires strong explicitly generated " + secret)

    origins = [o.strip() for o in environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
    _required(origins, "LAN requires explicit HTTPS CSRF origins")
    for origin in origins:
        u = urlsplit(origin)
        _required(u.scheme == "https" and not (u.username or u.password or u.path or u.query or u.fragment)
                  and u.hostname and u.hostname.lower() in hosts and (u.port in (None, 443)),
                  "LAN CSRF origins must be explicit HTTPS allowed hosts (port 443)")
    _required(any(urlsplit(origin).hostname == bind for origin in origins),
              "LAN must trust its configured bind origin")
    return {"profile": profile, "allowed_hosts": hosts, "csrf_origins": origins,
            "secure": True, "proxy_header": ("HTTP_X_FORWARDED_PROTO", "https")}
