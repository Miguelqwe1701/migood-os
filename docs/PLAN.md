# Migood OS – plan (2026-10-06)

Owner's ask: "Migood OS will be like a Googlebook UI themed". Update/download
endpoints are not shown on the website and are gated by Migood Beta.

## Next session: start here

The previous session's container broke mid-work (2026-10-07). Everything was
pushed to `claude/festive-noether-nzd8nt`, which is PR #1 and not merged yet. Still to do:

1. **Build**: `sudo bash build/build-iso.sh` (about an hour from scratch), then
   `sudo bash build/screenshot.sh`. Send the owner the screenshots (see CLAUDE.md).
2. **Not tested yet**:
   - Migood AI search provider inside the build: `chroot work/chroot dbus-run-session`,
     then `gdbus call ... GetInitialResultSet`.
   - Screenshots of the Calamares installer (`calamares -d` on Xvfb) and of the
     bunny-ears Migood button in the dock.
   - Settings additions (channel, Get help, Powerwash, battery), Migood Mail,
     Chromium start page and junior accounts. These are in the code but have
     never been built into an ISO.
3. **Needs a real VM** (owner: Codespace + `qemux/qemu`, see README): live boot,
   install with Calamares, first-boot setup, login screen, guest sign-out wipe through
   GDM, OTA update on the installed system.
4. **Container hygiene**: the build bind-mounts /proc, /sys and /dev into
   `work/chroot`. Always unmount them afterwards (`build-iso.sh` does), and don't run
   long tests with them mounted.

## Decision: Ubuntu + Cubic (not Windows + NTLite)

| | Ubuntu (Cubic) | Windows (NTLite) |
|---|---|---|
| Can we hand the ISO to others? | Yes, if Ubuntu trademarks are removed ("Migood OS, based on Ubuntu") | No, Microsoft's licence forbids it |
| Licence cost per PC | Free | A Windows licence each |
| Chromebook-style UI | GNOME + extensions | Hard |
| Migood desktop app | Yes (Linux build, 3.9.1+) | Yes |
| Windows games | Steam + Proton, Wine, or Remote Play | Native |
| Updates | apt + our OTA manifest | Windows Update only |

**Base:** Ubuntu 24.04 LTS, built on the command line (`build/build-iso.sh`, the same steps as Cubic), branded Migood OS.

## The look (Googlebook style, owner's update 2026-10-07)

- See-through top bar: time and date on the left, status icons and Quick Settings on the right
  (the `migood-shell` extension).
- Floating, centred dock at the bottom (Dash to Panel in dock mode): the Migood
  button first (the bunny-ears design the owner picked, `assets/migood-button.svg`), then apps.
- Launcher (ArcMenu) pops up from the dock: search on top, then an app grid.
- Dark, Nunito, Migood green `#2ecc71`.

## Owner's additions

- **Migood AI built in:** launcher search ("ask Migood AI…"), a shelf button, and
  actions it can take only after you confirm with a click (open apps, change
  settings, install apps, find files, start Remote Play, wake a PC). It can
  read logs to fix problems (with permission). Site rules apply: water limits,
  12-and-under filters, Coolness model picker, and no admin action without a
  password prompt.
- **Gaming profile:** gamemode, performance governor, low-latency kernel option,
  Proton/Wine, and controllers. **Streaming profile:** PipeWire screen + desktop
  audio, VA-API/NVENC, and Do Not Disturb while live.
- **Shop points** for playing and streaming are decided by the server only:
  `/api/shop/points`, `/api/shop/earn`, `/api/shop/redeem`. No idle farming,
  a daily cap, and no real money or trading for kids. The server session is building these.
- **Connection settings**: pick another Migood server on networks that block the main one.
  The Migood password unlocks the PC offline, and a PIN is optional.
- **The account matches Migood**: login name = Migood username, the name on the login screen =
  display name, picture = the Migood profile picture (synced at each login).

## ~50 features: status

✅ built · 🟡 partly / needs a real-PC test · 🌐 needs Migood server work first (other repo)

| # | Feature | Status |
|---|---|---|
| 1 | Migood sign-in on first boot = the computer account | ✅ setup (`migood-setup --oobe` + `create-account`) |
| 2 | Migood Games pinned + opens on login | ✅ pinned, autostart (full-screen "home" still an open question) |
| 3 | Shelf, launcher, Quick Settings | ✅ Googlebook-style dock + top bar |
| 4 | Migood wallpapers (seasonal) | 🌐 placeholder for now; needs a wallpaper feed |
| 5 | Green/dark theme, Nunito, rounded | ✅ |
| 6 | Guest mode (wiped on sign-out) | 🟡 wipe tested in the build; needs a real login test through GDM |
| 7 | 12-and-under protections | 🟡 junior accounts aren't admin; full parental controls with 38 |
| 8 | Setup wizard | ✅ welcome, Wi-Fi, sign in, PIN, tour |
| 9 | Boot logo | ✅ Plymouth |
| 10 | Low-RAM defaults | ✅ zram |
| 11 | Steam + Proton | 🟡 Steam installed; Proton is one click in Steam |
| 12 | Wine + Bottles | ✅ |
| 13 | Remote Play | ✅ via the Migood Games app (xdotool, PipeWire) |
| 14 | Controllers | ✅ steam-devices rules |
| 15 | Game Mode | 🟡 installed; on for games that request it |
| 16 | Emulators (no games) | ✅ RetroArch, Dolphin, PPSSPP |
| 17 | "Play on My PC" tiles | 🌐 |
| 18 | Wake your PC | 🌐 Linux version of wake.js (rtcwake service) |
| 19 | FPS overlay toggle | ✅ Settings → Gaming |
| 20 | Cloud saves | 🌐 |
| 21 | Migood notifications | 🟡 through the Migood Games app |
| 22 | Migood Mail as mail app | ✅ |
| 23 | Lives with PipeWire | ✅ PipeWire + the app |
| 24 | Discord status | ✅ in the app |
| 25 | Migood AI in launcher search | 🟡 built (`migood-ai`, `migood-ai-search`, `/api/ai/chat`), not tested in a running desktop yet |
| 26 | Friends in Quick Settings | 🌐 needs friends' online status (docs/SERVER_API.md) |
| 27 | Beta channel toggle | ✅ Settings → Updates |
| 28 | Get help with logs | ✅ Settings → Help (`/api/support/open`) |
| 29 | Migood status widget | 🌐 needs a status endpoint |
| 30 | OS achievements | 🌐 |
| 31 | OTA updates | ✅ daily check, install at shutdown |
| 32 | Stable + beta channels | ✅ |
| 33 | Rollback snapshots | ✅ Btrfs + Timeshift before each update |
| 34 | Signed manifests | 🟡 sha256 now, signing key later |
| 35 | Firewall | ✅ ufw on |
| 36 | Ubuntu security updates | ✅ unattended-upgrades |
| 37 | Full-disk encryption option | ✅ installer |
| 38 | Parental controls | 🌐 needs the account's rules from the server |
| 39 | Shared browser blocklist | 🌐 |
| 40 | Powerwash | ✅ Settings → Reset |
| 41 | Chromium + Migood start page | ✅ |
| 42 | Files + cloud drives | ✅ GNOME Files + Online Accounts |
| 43 | Waydroid (Android apps) | ⏳ later (experimental) |
| 44 | Phone link | ✅ GSConnect |
| 45 | Screenshot / record | ✅ GNOME (Print Screen) |
| 46 | On-screen keyboard, touch | ✅ GNOME |
| 47 | Battery saver, charge to 80% | ✅ power profiles + Settings → Battery |
| 48 | Printers | ✅ CUPS driverless |
| 49 | Accessibility | ✅ GNOME |
| 50 | "Migood OS" settings page | ✅ Migood OS Settings |

Also built: installer (Calamares), Migood Updates app, server picker for blocked
networks, PIN unlock, Migood display name + profile picture on the account.
What the OS calls on the server, and still needs, is in `docs/SERVER_API.md`.

## Server endpoints (already built on the Migood server: `osupdates.go`)

Every call needs a signed-in account (cookie or `Bearer` token) in the
`migood-os` Beta program, or an owner. Anyone else gets a plain 404.

```
GET  /api/os/latest?channel=stable|beta       newest release
GET  /api/os/updates?from=0.1.0&channel=      newer releases, oldest first
GET  /api/os/files/<name>                     ISO or bundle (Range resume)
POST /api/os/checkin {device,version,channel} record this device
GET  /api/os/devices                          caller's devices
POST /api/os/releases (owner) {version,channel,notes,files:[...]}
```

## Ground rules

- The owner is learning to code, so explain what you build and give small examples.
- Ask the owner before anything public, such as publishing a release or opening the Beta program.
- Never ship Windows bits, Ubuntu/Canonical logos, pirated games or ROMs.
  Call it "Migood OS (based on Ubuntu)".

## Owner's answers (2026-10-07)

- Build machine: no desktop needed. `build/build-iso.sh` builds on the command line,
  and GitHub Actions builds it and publishes to the Releases tab (it starts from the latest
  release ISO when there is one).
- Browser: **Chromium** (Flathub).
- Server: `https://www.welltypers.it.com`, with the fallback
  `https://wth5zs3z-3001.usw3.devtunnels.ms`.
- Assets come from the site (`/cdn/brand/`). The placeholder wallpaper is the
  guest wallpaper, and the main user's wallpaper for now.
- Show screenshots of the desktop during development (`build/screenshot.sh`).
- Migood button: "bunny ears" (C6 in `docs/design/launcher-options/`).
- Testing: a Codespace with Docker (`qemux/qemu`, needs `/dev/kvm`).

## Still open

- Should the Migood app open full screen as "home" on login?
- Who are the first testers?
