# Notes for Claude sessions working on Migood OS

Read `docs/PLAN.md` first: it has the decisions, the ~50-feature list and the open questions.

## Owner's standing requests
- **Show screenshots of the desktop while developing.** After any change to
  the look (theme, shelf, launcher, wallpaper), run `sudo bash build/build-iso.sh`
  then `sudo bash build/screenshot.sh`, and send the owner the PNGs from
  `docs/screenshots/`.
- The owner (Miguelqwe170) is learning to code, so explain what you build and give small examples.
- Ask before anything public: publishing a release, opening the Beta program.
- Never ship Windows bits, Ubuntu/Canonical logos, games or ROMs.

## Facts
- Migood server: `https://www.welltypers.it.com`. Cloudflare can block it;
  the fallback is `https://wth5zs3z-3001.usw3.devtunnels.ms` (dev tunnel). Both are in
  `overlay/etc/migood-os/update.conf` and `build/fetch-assets.sh`.
- Brand images: `<server>/cdn/brand/` (copied into `assets/`).
- Linux app: `<server>/downloads/desktop/latest-linux.yml`, fetched at build time.
- Browser: Chromium from Flathub (Ubuntu's chromium is a snap and can't install during the build).
- The wallpaper is a placeholder (`build/make-wallpaper.py`). It stays the guest
  wallpaper; the main user gets real Migood wallpapers later.
- Cubic is GUI-only, so `build/build-iso.sh` does the same thing from the command line.
  It works in a cloud container (root, no KVM) and on GitHub Actions.

## Container hygiene (learned the hard way)
- The build bind-mounts /proc, /sys and /dev into `work/chroot`. Unmount them
  (plain `umount`, not `-l`) as soon as a test is done; check with
  `mount | grep migood-os/work`.
- Never `pkill -f <pattern>` when the pattern is also in your own command
  line: it kills your own shell, and the cleanup after it never runs.
- Disk is tight (~30 GB): keep at most one base ISO + one output ISO.

## Checks before pushing
- `python3 -m unittest discover tests`
- `bash -n` on every script you changed
