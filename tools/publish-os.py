#!/usr/bin/env python3
"""Publish a Migood OS release to the Migood server, so Migood OS PCs get it.

  MIGOOD_OS_PUBLISH_KEY=... python3 tools/publish-os.py --version 0.1.5 \\
      [--channel beta] [--notes-file notes.md] [--app-version 3.11.0] \\
      [--min-from 0.1.0] [--rollout 0] [--mandatory] FILE [FILE ...]

1. Uploads each FILE (the ISO, the update bundle) in chunks of up to 64 MB,
   because Cloudflare refuses single requests over 100 MB. A dropped chunk is
   retried, and the server's "you're at byte N" (409) resumes the upload.
2. Publishes the release: version, channel, notes, files, settings.

The key comes ONLY from the MIGOOD_OS_PUBLISH_KEY environment variable (in
GitHub Actions: the repository secret of that name). It is never printed and
never put on a command line. Publishing reaches every Migood OS PC on that
channel: beta first, and stable only when the owner says so.
"""
import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("MIGOOD_PUBLISH_SERVER", "https://www.welltypers.it.com").rstrip("/")


def call(method, path, body=None, raw=None, timeout=300):
    """One request. Returns (status code, JSON answer)."""
    key = os.environ["MIGOOD_OS_PUBLISH_KEY"]
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={
        "Authorization": "Bearer " + key,
        "Content-Type": "application/octet-stream" if raw is not None else "application/json",
        "User-Agent": "migood-os-publish"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def upload(path, tries=5):
    name, size = os.path.basename(path), os.path.getsize(path)
    print(f"uploading {name} ({size} bytes)", flush=True)
    code, s = call("POST", "/api/os/publish/upload",
                   {"name": name, "size": size, "sha256": sha256_of(path)})
    if code == 200 and s.get("done"):
        print(f"  {name} is already on the server", flush=True)
        return s["file"]
    if code != 200:
        sys.exit(f"upload of {name} refused: {code} {s}")
    uid, got, step = s["id"], int(s.get("received", 0)), int(s["chunkMax"])
    failures = 0
    with open(path, "rb") as f:
        while got < size:
            f.seek(got)
            try:
                code, r = call("PUT", f"/api/os/publish/upload/{uid}?offset={got}", raw=f.read(step))
            except (urllib.error.URLError, OSError) as e:  # connection dropped mid-chunk
                code, r = 0, {"error": str(e)}
            if code in (200, 409) and "received" in r:  # 409 = carry on from the server's count
                got, failures = int(r["received"]), 0
                print(f"  {got * 100 // size}%", flush=True)
                continue
            failures += 1
            if failures >= tries:
                sys.exit(f"upload of {name} failed: {code} {r}")
            time.sleep(2 ** failures)
            code, r = call("GET", f"/api/os/publish/upload/{uid}")  # where did it get to?
            if code == 200 and "received" in r:
                got = int(r["received"])
    code, r = call("POST", f"/api/os/publish/upload/{uid}/finish")
    if code != 200:
        sys.exit(f"finishing {name} failed: {code} {r}"
                 + (" (bytes didn't match: thrown away, upload again)" if code == 422 else ""))
    return r["file"]


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--version", required=True)
    p.add_argument("--channel", default="beta", choices=["beta", "stable"])
    p.add_argument("--notes-file")
    p.add_argument("--app-version")
    p.add_argument("--min-from")
    p.add_argument("--rollout", type=int, default=0)
    p.add_argument("--mandatory", action="store_true")
    p.add_argument("files", nargs="+")
    a = p.parse_args(argv)
    if not os.environ.get("MIGOOD_OS_PUBLISH_KEY"):
        sys.exit("MIGOOD_OS_PUBLISH_KEY isn't set (GitHub: add it as a repository secret)")

    names = [upload(path)["name"] for path in a.files]
    settings = {"rollout": a.rollout, "mandatory": a.mandatory}
    if a.min_from:
        settings["minFrom"] = a.min_from
    if a.app_version:
        settings["appVersion"] = a.app_version
    notes = open(a.notes_file).read().strip() if a.notes_file else f"Migood OS {a.version}"
    code, r = call("POST", "/api/os/publish/release", {
        "version": a.version, "channel": a.channel, "notes": notes,
        "files": names, "settings": settings})
    if code != 200:
        sys.exit(f"publishing {a.version} failed: {code} {r}")
    print(f"published Migood OS {a.version} to the {a.channel} channel: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
