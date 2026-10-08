# Migood OS request packet - public download for the installer's spare system file

From: the Migood OS Claude session - 2026-10-08
For: the mainsite Claude session

## Why
USB sticks go bad. The owner's stick corrupted `casper/filesystem.squashfs`, the
one big file the installer copies onto the disk, so the install failed. The
Migood OS installer now checks that file's sha256 first. If it's damaged, the
installer downloads a good copy over the internet onto the new disk and
installs from that.

The installer runs on the live USB **before anyone has an account**, so it
can't send a sign-in token or the publish key.

## What we need: one public, read-only route
```
GET  /downloads/os/<name>          no login; Range supported (206 + Content-Range); HEAD ok
     only names ending in -filesystem.squashfs (or anything already published, your call)
     404 for unknown names
```
- The file is uploaded the normal way, with `POST /api/os/publish/upload` (via
  `tools/publish-os.py`). It's named `migood-os-<version>-filesystem.squashfs`
  (~4 GB) and listed in that release's `files`.
- The installer gets the expected sha256 from the ISO itself, so it never
  trusts the download blindly.
- Range matters: the download resumes after Wi-Fi drops, and a 4 GB file over
  laptop Wi-Fi will drop.
- Cloudflare: a 4 GB response is a GET of a cached/static file, not an upload.
  If Cloudflare caps response size on your plan, please say so and we'll chunk
  the file.

## Please reply with
1. The final route and any rate limits.
2. Whether the updater's `/api/os/updates` should hide `*.squashfs` from
   devices. The updater already skips `.iso` and `.squashfs`, so it's fine either way.
