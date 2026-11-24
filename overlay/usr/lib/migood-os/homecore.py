"""Migood Home's backend: everything the home screen asks the system for.

The home screen itself is HTML/CSS/JS (/usr/share/migood-home); it talks to
this module through migood-home's small bridge with messages like
{"cmd": "apps"} or {"cmd": "launch", "args": {"id": "steam.desktop"}}.
Only the commands in COMMANDS exist: the page can't run anything else.

No GTK in here, so the tests can run it anywhere. Paths are overridable with
environment variables for the same reason.
"""
import configparser
import glob
import json
import os
import pwd
import re
import subprocess
import time

HOME = os.path.expanduser("~")
APP_DIRS = os.environ.get("MIGOOD_APP_DIRS", ":".join([
    "/usr/share/applications",
    "/usr/local/share/applications",
    "/var/lib/flatpak/exports/share/applications",
    os.path.join(HOME, ".local/share/flatpak/exports/share/applications"),
    os.path.join(HOME, ".local/share/applications"),
])).split(":")
ICON_DIRS = os.environ.get("MIGOOD_ICON_DIRS", ":".join([
    os.path.join(HOME, ".local/share/icons"),
    "/var/lib/flatpak/exports/share/icons",
    "/usr/share/icons/hicolor", "/usr/share/icons/Yaru", "/usr/share/icons/Adwaita",
    "/usr/share/pixmaps",
])).split(":")
STATE = os.environ.get("MIGOOD_HOME_STATE", os.path.join(HOME, ".local/state/migood-home"))
AS_ICONS = os.environ.get("MIGOOD_AS_DIR", "/var/lib/AccountsService") + "/icons"
SYS_POWER = os.environ.get("MIGOOD_POWER_SUPPLY", "/sys/class/power_supply")

# Apps that are games even when their .desktop file doesn't say so.
GAME_IDS = ("steam", "migood-games", "retroarch", "dolphin", "ppsspp", "bottles", "lutris", "heroic")
# System bits nobody wants on a game console's home screen.
HIDE_IDS = ("org.gnome.Settings", "gnome-", "software-properties", "nm-connection-editor",
            "update-manager", "calamares", "yelp", "im-config", "debian-", "display-im6",
            "org.gnome.Extensions", "gnome-extensions", "info", "ibus", "gcr-", "org.freedesktop.")
# Migood's own apps get a fixed order on the home screen.
PINNED = ("migood-games.desktop", "org.chromium.Chromium.desktop", "steam.desktop")
TEXT_FIELDS = ("Name", "GenericName", "Comment")


def run(*cmd, timeout=10, input=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=input)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


# ---------- apps ----------

def read_desktop(path):
    cp = configparser.RawConfigParser(strict=False, interpolation=None)
    cp.optionxform = str  # keep "Name" as "Name"
    try:
        cp.read(path, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError):
        return None
    if not cp.has_section("Desktop Entry"):
        return None
    e = dict(cp.items("Desktop Entry"))
    if e.get("Type") != "Application" or e.get("NoDisplay") == "true" or e.get("Hidden") == "true":
        return None
    if not e.get("Exec") or not e.get("Name"):
        return None
    return e


_icon_cache = {}


def icon_path(name):
    """Icon name or path from a .desktop file -> an image file, or None."""
    if not name:
        return None
    if name.startswith("/"):
        return name if os.path.isfile(name) else None
    if name in _icon_cache:
        return _icon_cache[name]
    best, best_size = None, -1
    for base in ICON_DIRS:
        for path in glob.glob(f"{base}/**/{glob.escape(name)}.*", recursive=True):
            if not path.endswith((".png", ".svg")):
                continue
            m = re.search(r"/(\d+)x\d+/", path)
            size = 1000 if path.endswith(".svg") or "/scalable/" in path else int(m.group(1)) if m else 48
            if size > best_size:
                best, best_size = path, size
        if best and best_size >= 128:
            break
    _icon_cache[name] = best
    return best


def apps():
    """Every app a person would launch, games marked, Migood's first."""
    seen, out = set(), []
    for d in APP_DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*.desktop"))):
            app_id = os.path.basename(path)
            if app_id in seen or app_id.startswith(HIDE_IDS):
                continue
            e = read_desktop(path)
            if not e:
                continue
            seen.add(app_id)
            cats = [c for c in e.get("Categories", "").split(";") if c]
            low = app_id.lower()
            out.append({
                "id": app_id,
                "name": e["Name"],
                "comment": e.get("Comment", ""),
                "icon": icon_path(e.get("Icon")),
                "game": "Game" in cats or any(g in low for g in GAME_IDS),
                "path": path,
            })
    pin = {a: i for i, a in enumerate(PINNED)}
    out.sort(key=lambda a: (pin.get(a["id"], len(PINNED)), a["name"].lower()))
    return out


def app_path(app_id):
    """The .desktop file for an id from apps(): only real app files, no paths from the page."""
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+\.desktop", app_id or ""):
        return None
    for d in APP_DIRS:
        p = os.path.join(d, app_id)
        if os.path.isfile(p) and read_desktop(p):
            return p
    return None


# ---------- recently played ----------

def _recent_file():
    return os.path.join(STATE, "recent.json")


def recent(limit=8):
    try:
        with open(_recent_file()) as f:
            items = json.load(f)
    except (OSError, ValueError):
        return []
    return [i for i in items if isinstance(i, dict) and "id" in i][:limit]


def remember_launch(app_id, now=None):
    items = [i for i in recent(50) if i["id"] != app_id]
    items.insert(0, {"id": app_id, "at": int(now or time.time())})
    os.makedirs(STATE, exist_ok=True)
    tmp = _recent_file() + ".new"
    with open(tmp, "w") as f:
        json.dump(items[:50], f)
    os.replace(tmp, _recent_file())


# ---------- you ----------

def account():
    p = pwd.getpwuid(os.getuid())
    name = (p.pw_gecos.split(",")[0] or p.pw_name).strip()
    avatar = os.path.join(AS_ICONS, p.pw_name)
    signed_in = os.path.exists(os.path.join(HOME, ".config/migood/token"))
    return {"name": name, "user": p.pw_name,
            "avatar": avatar if os.path.isfile(avatar) else None, "signedIn": signed_in}


# ---------- status bar ----------

def battery():
    for d in sorted(glob.glob(os.path.join(SYS_POWER, "*"))):
        try:
            if open(os.path.join(d, "type")).read().strip() != "Battery":
                continue
            pct = int(open(os.path.join(d, "capacity")).read().strip())
            status = open(os.path.join(d, "status")).read().strip()
            return {"percent": pct, "charging": status in ("Charging", "Full")}
        except (OSError, ValueError):
            continue
    return None


def parse_nmcli(line):
    """nmcli -t output: fields split on ':' with '\\:' escaped."""
    return [p.replace("\\:", ":") for p in re.split(r"(?<!\\):", line)]


def wifi():
    code, out = run("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list")
    nets, seen = [], set()
    for line in out.splitlines():
        f = parse_nmcli(line)
        if len(f) < 4 or not f[1] or f[1] in seen:
            continue
        seen.add(f[1])
        nets.append({"ssid": f[1], "signal": int(f[2] or 0), "secure": bool(f[3]),
                     "connected": f[0] == "*"})
    nets.sort(key=lambda n: (not n["connected"], -n["signal"]))
    return nets


def wifi_connect(ssid, password=""):
    if not isinstance(ssid, str) or not ssid or len(ssid) > 64:
        return {"ok": False, "error": "bad network name"}
    cmd = ["nmcli", "dev", "wifi", "connect", ssid]
    if password:
        cmd += ["password", str(password)]
    code, out = run(*cmd, timeout=40)
    return {"ok": code == 0, "error": None if code == 0 else "Couldn't connect. Check the password."}


def status():
    code, out = run("nmcli", "-t", "-f", "TYPE,STATE", "dev")
    online = any(l.split(":")[1:2] == ["connected"] for l in out.splitlines())
    code, vol = run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
    m = re.search(r"Volume:\s*([\d.]+)", vol)
    return {"battery": battery(), "online": online,
            "volume": round(float(m.group(1)) * 100) if m else None, "muted": "MUTED" in vol}


def set_volume(percent):
    p = max(0, min(150, int(percent)))
    run("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{p}%")
    return {"ok": True, "volume": p}


# ---------- power and modes ----------

POWER = {
    "shutdown": ("systemctl", "poweroff"),
    "restart": ("systemctl", "reboot"),
    "sleep": ("systemctl", "suspend"),
}


def power(action):
    if action not in POWER:
        return {"ok": False, "error": "unknown action"}
    code, _ = run(*POWER[action])
    return {"ok": code == 0}


def set_session(session):
    """Which session the login screen starts for this user next time."""
    uid = os.getuid()
    for method in ("SetSession", "SetXSession"):
        run("gdbus", "call", "--system", "--dest", "org.freedesktop.Accounts",
            "--object-path", f"/org/freedesktop/Accounts/User{uid}",
            "--method", f"org.freedesktop.Accounts.User.{method}", session)


def log_out():
    sid = os.environ.get("XDG_SESSION_ID")
    if sid:
        run("loginctl", "terminate-session", sid)
    else:
        run("loginctl", "terminate-user", str(os.getuid()))


def home_mode():
    """From the desktop: next session is Migood Home, then log out."""
    set_session("migood-home")
    log_out()
    return {"ok": True}


def desktop_mode():
    """Switch to the full desktop: next session is the desktop, then log out."""
    set_session("ubuntu")
    log_out()
    return {"ok": True}


COMMANDS = {
    "apps": lambda a: apps(),
    "recent": lambda a: recent(int(a.get("limit", 8))),
    "account": lambda a: account(),
    "status": lambda a: status(),
    "wifi": lambda a: wifi(),
    "wifi_connect": lambda a: wifi_connect(a.get("ssid"), a.get("password", "")),
    "volume": lambda a: set_volume(a.get("percent", 50)),
    "power": lambda a: power(a.get("action")),
    "desktop_mode": lambda a: desktop_mode(),
}


def handle(cmd, args=None):
    """One request from the page. Unknown commands are refused."""
    fn = COMMANDS.get(cmd)
    if not fn:
        return {"error": f"unknown command {cmd!r}"}
    try:
        return fn(args if isinstance(args, dict) else {})
    except Exception as e:  # never crash the home screen over one request
        return {"error": str(e)}
