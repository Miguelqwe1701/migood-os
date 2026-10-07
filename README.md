# Migood OS

Ubuntu-based OS for Migood Games. It's ChromeOS-style: a shelf at the bottom,
a full-screen launcher, Migood green and dark. The full plan is in
[docs/PLAN.md](docs/PLAN.md).

## Getting the ISO

You don't need a computer for this. GitHub builds it:

- **Actions tab → "Build Migood OS" → Run workflow**, then type a version like `0.1.0`.
- Or push a tag: `git tag v0.1.0 && git push origin v0.1.0`.

About an hour later the ISO shows up on the **Releases** tab as a pre-release.

To build it yourself instead, use an Ubuntu 24.04 machine or VM with about 30 GB free:

```bash
sudo bash build/build-iso.sh          # -> out/migood-os-0.1.0.iso
```

## What's in here

| Path | What it does |
|---|---|
| `build/build-iso.sh` | Builds the ISO from scratch: debootstrap → install desktop → customize → squashfs → bootable ISO (BIOS + UEFI). This replaces clicking through Cubic. |
| `cubic/customize.sh` | Turns plain Ubuntu into Migood OS: packages, theme, branding, os-release, boot logo, Migood app. It also works by hand inside Cubic. |
| `overlay/` | Files copied onto the OS as they are (`overlay/etc/x` ends up as `/etc/x`). |
| `overlay/usr/lib/migood-os/update` | The OTA updater (Python). `check` runs daily, `apply` runs at shutdown, and `checkin` reports to the server. |
| `overlay/etc/dconf/db/local.d/00-migood` | Desktop defaults: shelf, launcher, dark theme, Nunito. |
| `assets/` | Images and the Migood desktop app (see below). |
| `tests/` | Updater tests against a fake Migood server: `python3 -m unittest discover tests` |

## Assets to add

The build still works if these are missing. You just get a warning and the default look.

- `assets/migood-square.png`: boot logo (from `/public/cdn/brand/` on the site)
- `assets/migood-launcher.svg`: Migood logo for the launcher button
- `assets/wallpaper.png`: default wallpaper
- `assets/migood-games-<version>.tar.gz`: the Linux desktop app build
  (`npm run electron-builder --linux tar.gz`)

Never add Windows files, Ubuntu/Canonical logos, games or ROMs.

## How updates work

1. Every day the OS asks the server `GET /api/os/updates?from=<its version>&channel=beta`.
2. It downloads each new bundle and checks the bundle's sha256. A broken download is thrown away and tried again later.
3. At shutdown it takes a Timeshift snapshot, installs each bundle oldest-first, and
   bumps the version. If anything fails, the version stays the same and it retries next time.

A bundle is a `.tar.gz` with a `debs/` folder (packages to install) and/or an
`apply.sh` script.
