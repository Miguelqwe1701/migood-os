#!/usr/bin/env python3
"""Calamares job: make sure the system file on the USB stick is good, and
replace it over the internet when it isn't.

USB sticks go bad. The whole Migood OS is one big file on the stick,
casper/filesystem.squashfs; if a part of it can't be read, the install fails
half-way. This job runs three times (three instances in settings.conf):

  verify   FIRST, before the disk is touched. Reads the whole file and compares
           its sha256 with casper/filesystem.squashfs.sha256 (written when the
           ISO was built). Damaged and no internet: stop here, the disk is
           untouched. Damaged with internet: remember it for "repair".
  repair   after the disk is partitioned and mounted. Downloads a good copy from
           the Migood server onto the NEW disk (PCs like the 4 GB Asus can't hold
           4 GB in memory), resumes if the download drops, checks the sha256,
           and mounts it over the broken file. The normal copy step (unpackfs)
           then reads the good one without knowing anything changed.
  cleanup  after the copy: unmount and delete the downloaded file.
"""
import errno
import hashlib
import http.client
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

import libcalamares

sys.path.insert(0, "/usr/lib/migood-os")
try:
    import migoodlib  # server list (same as Settings -> Connection)
except ImportError:  # tests, or a very old image
    migoodlib = None

CDROM = "/cdrom"
SQUASH = "casper/filesystem.squashfs"
DOWNLOAD = "var/tmp/migood-filesystem.squashfs"  # inside the new disk
BLOCK = 4 << 20


def cfg(key, default=None):
    return (libcalamares.job.configuration or {}).get(key, default)


def pretty_name():
    return "Check the USB stick"


def paths():
    cdrom = cfg("cdrom", CDROM)
    return os.path.join(cdrom, SQUASH), os.path.join(cdrom, SQUASH + ".sha256")


def expected():
    """(sha256, server file name) from the ISO, or (None, None) on old ISOs."""
    _, sumfile = paths()
    try:
        with open(sumfile) as f:
            sha, name = f.read().split()[:2]
        return sha.lower(), os.path.basename(name)
    except (OSError, ValueError):
        return None, None


def file_ok(path, sha, progress_share):
    """True if the file reads all the way through and matches sha256."""
    h = hashlib.sha256()
    try:
        size = os.path.getsize(path)
        done = 0
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(BLOCK), b""):
                h.update(block)
                done += len(block)
                libcalamares.job.setprogress(progress_share * done / max(size, 1))
    except OSError as e:  # missing, or an I/O error from a damaged stick
        libcalamares.utils.warning(f"migoodcheck: can't read {path}: {e}")
        return False
    return h.hexdigest() == sha


def servers():
    if cfg("servers"):
        return list(cfg("servers"))
    if migoodlib:
        return migoodlib.servers()
    return ["https://www.welltypers.it.com", "https://wth5zs3z-3001.usw3.devtunnels.ms"]


def urls(name):
    for s in servers():
        yield f"{s.rstrip('/')}/downloads/os/{name}"


def online():
    for s in servers():
        try:
            urllib.request.urlopen(urllib.request.Request(s, method="HEAD"), timeout=10).close()
            return True
        except urllib.error.HTTPError:
            return True  # something answered: the internet works
        except (urllib.error.URLError, OSError):
            continue
    return False


def download(name, dest, sha):
    """Download with resume; True when dest matches sha256."""
    part = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for url in urls(name):
        for _attempt in range(5):
            have = os.path.getsize(part) if os.path.exists(part) else 0
            req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    if r.status == 200 and have:
                        have = 0  # the server sent the whole file again
                    total = have + int(r.headers.get("Content-Length") or 0)
                    free = shutil.disk_usage(os.path.dirname(dest)).free
                    if total - have > free:
                        raise OSError(errno.ENOSPC, "not enough space on the new disk")
                    with open(part, "ab" if have else "wb") as f:
                        while True:
                            block = r.read(1 << 20)
                            if not block:
                                break
                            f.write(block)
                            have += len(block)
                            libcalamares.job.setprogress(min(0.99, have / max(total, 1)))
                if have < total:  # the connection ended early: resume from here
                    raise http.client.IncompleteRead(b"", total - have)
                break
            except urllib.error.HTTPError as e:
                if e.code == 416:  # we already have every byte
                    break
                libcalamares.utils.warning(f"migoodcheck: {url}: {e}")
                break  # this server doesn't have it: try the next one
            except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
                if getattr(e, "errno", None) == errno.ENOSPC:
                    raise
                libcalamares.utils.warning(f"migoodcheck: {url} dropped ({e}), resuming")
        if os.path.exists(part):
            if file_ok(part, sha, 1.0):
                os.replace(part, dest)
                return True
            os.remove(part)  # a bad download: try the next server from scratch
    return False


def run_cmd(*cmd):
    return subprocess.run(cmd, check=True)


def verify():
    squash, _ = paths()
    sha, name = expected()
    if not sha:
        libcalamares.utils.warning("migoodcheck: no sha256 on this ISO, not checking")
        return None
    libcalamares.globalstorage.insert("migoodSquash", {"sha": sha, "name": name})
    if file_ok(squash, sha, 1.0):
        libcalamares.globalstorage.insert("migoodNeedsRepair", False)
        return None
    libcalamares.globalstorage.insert("migoodNeedsRepair", True)
    if not online():
        return ("The USB stick is damaged",
                "Part of Migood OS on this USB stick can't be read, so it can't be installed "
                "from it. Nothing on your disk was changed.<br/><br/>"
                "Connect to Wi-Fi and press Install again: Migood OS will download the "
                "damaged part. Or write the ISO to the stick again (or use another stick).")
    return None


def repair():
    if not libcalamares.globalstorage.value("migoodNeedsRepair"):
        return None
    info = libcalamares.globalstorage.value("migoodSquash") or {}
    root = libcalamares.globalstorage.value("rootMountPoint")
    dest = os.path.join(root, DOWNLOAD)
    try:
        ok = download(info["name"], dest, info["sha"])
    except OSError as e:
        return ("Couldn't download Migood OS", f"{e}. Write the ISO to the USB stick again and retry.")
    if not ok:
        return ("Couldn't download Migood OS",
                "The USB stick is damaged and a good copy couldn't be downloaded (no internet, "
                "or the Migood server didn't answer). Write the ISO to the stick again and retry.")
    squash, _ = paths()
    run_cmd("mount", "--bind", dest, squash)  # unpackfs now reads the good copy
    libcalamares.globalstorage.insert("migoodRepaired", dest)
    return None


def cleanup():
    dest = libcalamares.globalstorage.value("migoodRepaired")
    if not dest:
        return None
    squash, _ = paths()
    try:
        run_cmd("umount", squash)
    except (OSError, subprocess.CalledProcessError) as e:
        libcalamares.utils.warning(f"migoodcheck: umount: {e}")
    for f in (dest, dest + ".part"):
        try:
            os.remove(f)
        except FileNotFoundError:
            pass
    return None


def run():
    mode = cfg("mode", "verify")
    return {"verify": verify, "repair": repair, "cleanup": cleanup}[mode]()
