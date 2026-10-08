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

The same check also runs BEFORE Calamares starts (migood-install calls
`python3 main.py --check`), in a window with a "Skip" button. Its answer is
saved in /run/migood-os/usb-check, so "verify" doesn't read 4 GB a second time
(and a retry after a failed install starts straight away).

Every step is wrapped so a Python error becomes a normal "couldn't install"
message in the installer instead of taking it down.
"""
import errno
import hashlib
import http.client
import os
import queue
import shutil
import subprocess
import sys
import threading
import traceback
import urllib.error
import urllib.request

try:
    import libcalamares
except ImportError:  # run from the command line (migood-install --check)
    libcalamares = None

sys.path.insert(0, "/usr/lib/migood-os")
try:
    import migoodlib  # server list (same as Settings -> Connection)
except ImportError:  # tests, or a very old image
    migoodlib = None

CDROM = "/cdrom"
SQUASH = "casper/filesystem.squashfs"
DOWNLOAD = "var/tmp/migood-filesystem.squashfs"  # inside the new disk
BLOCK = 8 << 20
# Result of the check, shared between migood-install and the Calamares job.
# /run is wiped at every start-up, so a re-written stick is always re-checked.
RESULT = os.environ.get("MIGOOD_USB_CHECK", "/run/migood-os/usb-check")
LOG_HINT = ("<br/><br/>Nothing else was changed. The installer log is saved on the "
            "desktop as <b>migood-installer-log.txt</b>.")


# --- small helpers that work with and without Calamares --------------------

def cfg(key, default=None):
    if libcalamares is None:
        return default
    return (libcalamares.job.configuration or {}).get(key, default)


def warn(msg):
    if libcalamares is not None:
        libcalamares.utils.warning(msg)
    else:
        print(msg, file=sys.stderr)


def gs_get(key):
    return libcalamares.globalstorage.value(key) if libcalamares else None


def gs_set(key, value):
    if libcalamares:
        libcalamares.globalstorage.insert(key, value)


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


def read_result(sha):
    """'ok', 'skipped' or 'damaged' if this stick was already checked."""
    try:
        with open(RESULT) as f:
            got_sha, status = f.read().split()[:2]
        return status if got_sha == sha else None
    except (OSError, ValueError):
        return None


def write_result(sha, status):
    try:
        os.makedirs(os.path.dirname(RESULT), exist_ok=True)
        with open(RESULT, "w") as f:
            f.write(f"{sha} {status}\n")
    except OSError as e:
        warn(f"migoodcheck: can't save the result: {e}")


def file_ok(path, sha, progress=None):
    """True if the file reads all the way through and matches sha256.

    Faster than a plain loop: one thread reads the stick while this one
    hashes, so the USB stick never waits for the CPU (hashlib lets go of
    Python's lock while it hashes). Big blocks + 'sequential' advice make
    the kernel read ahead.
    """
    h = hashlib.sha256()
    blocks = queue.Queue(maxsize=4)
    failed = []

    def reader():
        try:
            with open(path, "rb", buffering=0) as f:
                try:
                    os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_SEQUENTIAL)
                except (AttributeError, OSError):
                    pass
                while True:
                    block = f.read(BLOCK)
                    blocks.put(block)
                    if not block:
                        return
        except OSError as e:  # missing, or an I/O error from a damaged stick
            failed.append(e)
            blocks.put(b"")

    try:
        size = os.path.getsize(path)
    except OSError as e:
        warn(f"migoodcheck: can't read {path}: {e}")
        return False
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    done, last = 0, -1
    while True:
        block = blocks.get()
        if not block:
            break
        h.update(block)
        done += len(block)
        pct = int(100 * done / max(size, 1))
        if progress and pct != last:  # at most 100 updates, not thousands
            last = pct
            progress(done / max(size, 1))
    t.join()
    if failed:
        warn(f"migoodcheck: can't read {path}: {failed[0]}")
        return False
    return h.hexdigest() == sha


def job_progress(share=1.0):
    if libcalamares is None:
        return None
    return lambda f: libcalamares.job.setprogress(share * f)


def servers():
    if cfg("servers"):
        return list(cfg("servers"))
    if migoodlib:
        try:
            return migoodlib.servers()
        except Exception as e:  # a broken update.conf must not stop the install
            warn(f"migoodcheck: server list: {e}")
    return ["https://www.welltypers.it.com", "https://wth5zs3z-3001.usw3.devtunnels.ms"]


def urls(name):
    for s in servers():
        yield f"{s.rstrip('/')}/downloads/os/{name}"


def online():
    for s in servers():
        try:
            urllib.request.urlopen(urllib.request.Request(s, method="HEAD"), timeout=8).close()
            return True
        except urllib.error.HTTPError:
            return True  # something answered: the internet works
        except (urllib.error.URLError, OSError, ValueError):
            continue
    return False


def download(name, dest, sha):
    """Download with resume; True when dest matches sha256."""
    part = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    prog = job_progress()
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
                            if prog:
                                prog(min(0.99, have / max(total, 1)))
                if have < total:  # the connection ended early: resume from here
                    raise http.client.IncompleteRead(b"", total - have)
                break
            except urllib.error.HTTPError as e:
                if e.code == 416:  # we already have every byte
                    break
                warn(f"migoodcheck: {url}: {e}")
                break  # this server doesn't have it: try the next one
            except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as e:
                if getattr(e, "errno", None) == errno.ENOSPC:
                    raise
                warn(f"migoodcheck: {url} dropped ({e}), resuming")
        if os.path.exists(part):
            if file_ok(part, sha, prog):
                os.replace(part, dest)
                return True
            os.remove(part)  # a bad download: try the next server from scratch
    return False


def run_cmd(*cmd):
    return subprocess.run(cmd, check=True)


# --- the three steps --------------------------------------------------------

def verify():
    squash, _ = paths()
    sha, name = expected()
    if not sha:
        warn("migoodcheck: no sha256 on this ISO, not checking")
        return None
    gs_set("migoodSquash", {"sha": sha, "name": name})
    status = read_result(sha)  # already checked (or skipped) before Calamares started
    if status in ("ok", "skipped"):
        gs_set("migoodNeedsRepair", False)
        return None
    if status != "damaged":
        status = "ok" if file_ok(squash, sha, job_progress()) else "damaged"
        write_result(sha, status)
    if status == "ok":
        gs_set("migoodNeedsRepair", False)
        return None
    gs_set("migoodNeedsRepair", True)
    if not online():
        return ("The USB stick is damaged",
                "Part of Migood OS on this USB stick can't be read, so it can't be installed "
                "from it. Nothing on your disk was changed.<br/><br/>"
                "Connect to Wi-Fi and press Install again: Migood OS will download the "
                "damaged part. Or write the ISO to the stick again (or use another stick).")
    return None


def repair():
    if not gs_get("migoodNeedsRepair"):
        return None
    info = gs_get("migoodSquash") or {}
    root = gs_get("rootMountPoint")
    if not root or not info.get("name") or not info.get("sha"):
        return ("Couldn't install Migood OS",
                "The new disk wasn't ready for the download (no mount point)." + LOG_HINT)
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
    try:
        run_cmd("mount", "--bind", dest, squash)  # unpackfs now reads the good copy
    except (OSError, subprocess.CalledProcessError) as e:
        return ("Couldn't install Migood OS", f"The downloaded copy couldn't be used: {e}." + LOG_HINT)
    gs_set("migoodRepaired", dest)
    return None


def cleanup():
    dest = gs_get("migoodRepaired")
    if not dest:
        return None
    squash, _ = paths()
    try:
        run_cmd("umount", squash)
    except (OSError, subprocess.CalledProcessError) as e:
        warn(f"migoodcheck: umount: {e}")
    for f in (dest, dest + ".part"):
        try:
            os.remove(f)
        except OSError:
            pass
    return None


def run():
    mode = cfg("mode", "verify")
    step = {"verify": verify, "repair": repair, "cleanup": cleanup}.get(mode)
    if step is None:
        return ("Installer setup error", f"migoodcheck: unknown mode {mode!r}")
    try:
        return step()
    except Exception as e:  # never crash the installer: show a message instead
        warn("migoodcheck: " + traceback.format_exc())
        if mode == "cleanup":
            return None  # the install itself is done; a leftover temp file is harmless
        return ("Couldn't install Migood OS", f"The USB check stopped with an error: {e}" + LOG_HINT)


# --- command line: the check with a progress bar, before Calamares ----------

def cli_check():
    """Prints 0..100 lines (for `zenity --progress`), then saves the result.
    Exit code: 0 good / no fingerprint, 1 damaged."""
    sha, _ = expected()
    if not sha:
        print("100", flush=True)
        return 0
    status = read_result(sha)
    if status in ("ok", "skipped"):
        print("100", flush=True)
        return 0
    if status != "damaged":
        squash, _ = paths()
        print("# Checking the USB stick (you can skip this)...", flush=True)
        ok = file_ok(squash, sha, lambda f: print(int(f * 99), flush=True))
        status = "ok" if ok else "damaged"
        write_result(sha, status)
    print("100", flush=True)
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    if sys.argv[1:2] == ["--check"]:
        sys.exit(cli_check())
    if sys.argv[1:2] == ["--skip"]:
        sha, _ = expected()
        if sha:
            write_result(sha, "skipped")
        sys.exit(0)
    print("usage: main.py --check | --skip", file=sys.stderr)
    sys.exit(2)
