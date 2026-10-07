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

## Trying it

- **VirtualBox / VMware:** new "Ubuntu (64-bit)" VM, 4 GB+ RAM, 30 GB disk, ISO as the CD.
- **USB stick:** write the ISO with balenaEtcher or Rufus and boot from it.
- **GitHub Codespace (Docker):** runs a virtual machine inside Docker and shows the
  screen in your browser on port 8006. Check `ls /dev/kvm` first, or it will be very slow:

  ```bash
  docker run -it --rm -p 8006:8006 --device=/dev/kvm --device=/dev/net/tun \
    --cap-add NET_ADMIN -e RAM_SIZE=6G -e CPU_CORES=4 \
    -v "$PWD/migood-os-0.1.0.iso:/boot.iso" qemux/qemu
  ```

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
