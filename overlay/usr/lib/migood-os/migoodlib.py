"""Shared helpers for the Migood OS apps (setup, settings).

The server list lives in /etc/migood-os/update.conf (SERVERS=...), the same
file the updater reads. Servers are tried in order: if one is blocked (a
hotel or school network, Cloudflare's bot check) the next one is used.
"""
import json
import os
import re
import urllib.error
import urllib.request

CONF = os.environ.get("MIGOOD_CONF", "/etc/migood-os/update.conf")
MAIN = "https://www.welltypers.it.com"
BACKUP = "https://wth5zs3z-3001.usw3.devtunnels.ms"
KNOWN = [("Main (welltypers.it.com)", MAIN), ("Backup (dev tunnel)", BACKUP)]
BLOCKED = {403, 429, 502, 503, 504, 520, 521, 522, 523, 524, 525, 526}
URL_RE = re.compile(r"^https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?/?$")

# Setup can try a server before it's saved (e.g. on the live USB).
override = None


def valid_url(url):
    return bool(URL_RE.match(url.strip()))


def servers():
    if override:
        return list(override)
    try:
        with open(CONF) as f:
            for line in f:
                line = line.strip()
                if line.startswith("SERVERS="):
                    found = [s.rstrip("/") for s in line.split("=", 1)[1].split() if valid_url(s)]
                    if found:
                        return found
    except OSError:
        pass
    return [MAIN, BACKUP]


def api(path, body=None, token=None, only=None, timeout=20):
    """Call the Migood server. `only` = try just that one server."""
    last = None
    for base in ([only] if only else servers()):
        headers = {"User-Agent": "migood-os", "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            req = urllib.request.Request(base.rstrip("/") + path, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in BLOCKED:
                last = e
                continue
            try:
                msg = json.load(e).get("error")
            except Exception:
                msg = None
            raise RuntimeError(msg or f"Server said {e.code}")
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = e
    raise RuntimeError("Can't reach Migood. Try another server in Connection settings."
                       if last else "No server set")


def test_server(url):
    """True if `url` answers like a Migood server. /api/me says 401 "Not logged in"."""
    try:
        api("/api/me", only=url.rstrip("/"), timeout=10)
        return True
    except RuntimeError as e:
        return "logged in" in str(e).lower()


def sign_in(username, password):
    """Returns (token, profile). Raises RuntimeError with a friendly message."""
    res = api("/api/auth/token", {"username": username, "password": password})
    token = res.get("token") or res.get("access_token")
    if not token:
        raise RuntimeError(res.get("error") or "Sign-in failed")
    try:
        me = api("/api/me", token=token)
    except RuntimeError:
        me = {}
    return token, me
