# Migood OS

Ubuntu-based OS for Migood Games. It's ChromeOS-style: a shelf at the bottom,
a full-screen launcher, Migood green and dark. The full plan is in
[docs/PLAN.md](docs/PLAN.md).

## Getting the ISO

You don't need a computer for this. GitHub builds it:

- **Actions tab → "Build Migood OS" → Run workflow**, then type a version like `0.1.0`.
- Or push a tag: `git tag v0.1.0 && git push origin v0.1.0`.

About an hour later the ISO shows up on the **Releases** tab as a pre-release.
It's over GitHub's 2 GB file limit, so it comes in parts. Download all the parts and the
`.sha256` file into one folder, then join them with `tools/merge-iso.bat` (Windows,
double-click; keep `merge-iso.ps1` next to it) or `bash tools/merge-iso.sh` (Linux/macOS).
New releases include these scripts next to the parts.

To build it yourself instead, use an Ubuntu 24.04 machine or VM with about 30 GB free:

```bash
sudo bash build/build-iso.sh          # -> out/migood-os-0.1.0.iso
```

## Trying it

- **VirtualBox / VMware:** new "Ubuntu (64-bit)" VM, 4 GB+ RAM, 30 GB disk, ISO as the CD.
- **USB stick:** write the ISO with balenaEtcher or Rufus and boot from it.
- **GitHub Codespace (Docker):** open this repo in a Codespace (4+ cores; the
  `.devcontainer` sets up Docker and the GitHub CLI), then run:

  ```bash
  bash vm/start.sh
  ```

  It downloads the newest ISO from Releases (joining the parts), starts a virtual
  machine with `vm/docker-compose.yml`, and shows its screen on **port 8006**
  (Ports tab). The VM's 40 GB disk is kept in `vm/storage/`, so you can install Migood OS
  and reboot into it. If `/dev/kvm` is missing it still works, but very slowly.

## What's in here

| Path | What it does |
|---|---|
| `build/build-iso.sh` | Builds the ISO from scratch: debootstrap → install desktop → customize → squashfs → bootable ISO (BIOS + UEFI). This replaces clicking through Cubic. |
| `build/screenshot.sh` | Starts the built desktop on a virtual screen and saves screenshots to `docs/screenshots/`. |
| `build/fetch-assets.sh` | Downloads the newest Migood Games Linux app from the site. |
| `build/make-wallpaper.py` | Makes the placeholder wallpaper. |
| `cubic/customize.sh` | Turns plain Ubuntu into Migood OS: packages, theme, branding, os-release, boot logo, Migood app. It also works by hand inside Cubic. |
| `overlay/` | Files copied onto the OS as they are (`overlay/etc/x` ends up as `/etc/x`). |
| `overlay/usr/lib/migood-os/update` | The OTA updater (Python). `check` runs daily, `apply` runs at shutdown, and `checkin` reports to the server. |
| `overlay/etc/dconf/db/local.d/00-migood` | Desktop defaults: shelf, launcher, dark theme, Nunito. |
| `assets/` | Images and the Migood desktop app (see below). |
| `tools/merge-iso.*` | Join the downloaded ISO parts back into one `.iso` and check it. |
| `vm/` | Run the ISO in a virtual machine inside Docker (`bash vm/start.sh`). |
| `tests/` | Updater tests against a fake Migood server: `python3 -m unittest discover tests` |

## Assets

- `assets/migood-square.png`, `assets/migood-logo.png`: from the site's `/cdn/brand/`
  (boot logo, launcher button, wallpaper wordmark)
- `assets/wallpaper.png`: placeholder made by `build/make-wallpaper.py`
- The Migood Games Linux app is downloaded at build time (not stored in git).

Never add Windows files, Ubuntu/Canonical logos, games or ROMs.

## How updates work

1. Every day the OS asks the server `GET /api/os/updates?from=<its version>&channel=beta`.
2. It downloads each new bundle and checks the bundle's sha256. A broken download is thrown away and tried again later.
3. At shutdown it takes a Timeshift snapshot, installs each bundle oldest-first, and
   bumps the version. If anything fails, the version stays the same and it retries next time.

A bundle is a `.tar.gz` with a `debs/` folder (packages to install) and/or an
`apply.sh` script.
