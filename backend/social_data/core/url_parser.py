import re
from urllib.parse import unquote, urlparse

from .errors import InvalidProfileUrl

_PATTERNS = {
    "tiktok": (
        {"tiktok.com", "www.tiktok.com", "m.tiktok.com"},
        re.compile(r"^/@(?P<handle>[A-Za-z0-9_.]{2,24})/?$"),
    ),
    "instagram": (
        {"instagram.com", "www.instagram.com"},
        re.compile(r"^/(?P<handle>[A-Za-z0-9_.]{1,30})/?$"),
    ),
    "youtube": (
        {"youtube.com", "www.youtube.com", "m.youtube.com"},
        re.compile(r"^/(?:@(?P<handle>[\w.\-·]{3,30})|channel/(?P<channel>UC[A-Za-z0-9_\-]{22}))/?(?:shorts/?)?$"),
    ),
}
_RESERVED_INSTAGRAM = {"p", "reel", "reels", "explore", "stories", "accounts", "direct"}


def detect_platform(url: str) -> tuple[str, str]:
    """Return (platform, handle-or-channel-id) for a profile URL, or raise InvalidProfileUrl."""
    if not isinstance(url, str) or len(url) > 500:
        raise InvalidProfileUrl("bad url")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise InvalidProfileUrl("scheme")
    host = (parsed.hostname or "").lower()
    for platform, (hosts, pattern) in _PATTERNS.items():
        if host in hosts:
            m = pattern.match(unquote(parsed.path))
            if not m:
                raise InvalidProfileUrl("path")
            ident = m.groupdict().get("handle") or m.groupdict().get("channel")
            if platform == "instagram" and ident.lower() in _RESERVED_INSTAGRAM:
                raise InvalidProfileUrl("reserved path")
            return platform, ident
    raise InvalidProfileUrl("unsupported host")
