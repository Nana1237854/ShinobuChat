import ipaddress
import socket
from urllib.parse import urlparse

from app.core.exceptions import BadRequestError

_PRIVATE_NETWORKS = [
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("169.254.0.0/16"),
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fc00::/7"),
    ipaddress.IPv6Network("fe80::/10"),
]

_UNSAFE_HOSTNAMES = {
    "localhost",
    "0.0.0.0",
}


def _is_private_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return any(addr in net for net in _PRIVATE_NETWORKS)


def validate_url_safe(url_str: str) -> None:
    parsed = urlparse(url_str)
    if parsed.scheme not in {"http", "https"}:
        raise BadRequestError("URL scheme must be http or https")
    hostname = parsed.hostname
    if not hostname:
        raise BadRequestError("URL has no valid hostname")
    if hostname.lower() in _UNSAFE_HOSTNAMES:
        raise BadRequestError(f"URL targets a disallowed host: {hostname}")

    if hostname == "0.0.0.0":
        raise BadRequestError("URL targets a disallowed host")

    try:
        addrs = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise BadRequestError(f"Failed to resolve hostname: {hostname}") from exc

    seen_ips: set[str] = set()
    for family, _, _, _, sockaddr in addrs:
        ip = sockaddr[0]
        if ip not in seen_ips:
            seen_ips.add(ip)
            if _is_private_ip(ip):
                raise BadRequestError(
                    f"URL targets a private or reserved IP address ({ip}). "
                    f"Public URLs only."
                )
