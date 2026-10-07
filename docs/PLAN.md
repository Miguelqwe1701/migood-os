# Migood OS – plan (2026-10-06)

Owner's ask: "Migood OS will be like a Googlebook UI themed". Update/download
endpoints are not shown on the website and are gated by Migood Beta.

## Decision: Ubuntu + Cubic (not Windows + NTLite)

| | Ubuntu (Cubic) | Windows (NTLite) |
|---|---|---|
| Can we hand the ISO to others? | Yes, if Ubuntu trademarks are removed ("Migood OS, based on Ubuntu") | No, Microsoft's licence forbids it |
| Licence cost per PC | Free | A Windows licence each |
| Chromebook-style UI | GNOME + extensions | Hard |
| Migood desktop app | Yes (Linux build, 3.9.1+) | Yes |
| Windows games | Steam + Proton, Wine, or Remote Play | Native |
| Updates | apt + our OTA manifest | Windows Update only |

**Base:** Ubuntu 24.04 LTS, built with Cubic, branded Migood OS.

## The look (ChromeOS style)

- Shelf at the bottom that looks like the Migood app's taskbar: Migood logo
  launcher on the left, pinned and running apps as rounded pills, clock on the
  right, dark glass `rgba(10,13,18,.85)` + blur, Nunito, Migood green `#2ecc71`.
- Launcher: a full-screen grid with search on top.
- Quick Settings in the bottom-right corner.
- Built from GNOME + Dash to Panel + ArcMenu + our theme.

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
  a daily cap, and no real money or trading for kids.

## ~50 features (rough build order)

Out of the box: 1 Migood sign-in on first boot · 2 Migood Games app pinned and
opened on login · 3 shelf/launcher/quick settings · 4 Migood wallpapers
(seasonal) · 5 green/dark theme, Nunito, rounded · 6 Guest mode · 7
12-and-under protections · 8 4-screen setup wizard · 9 Plymouth Migood logo ·
10 low-RAM defaults (zram).

Games: 11 Steam + Proton · 12 Wine + Bottles · 13 Remote Play host/client · 14
controllers · 15 gamemode · 16 RetroArch/Dolphin/PPSSPP (no games) · 17 "Play
on My PC" tiles · 18 wake your PC · 19 MangoHud · 20 cloud saves.

Migood built in: 21 Migood notifications · 22 Migood Mail · 23 Lives with
PipeWire · 24 Discord status · 25 Migood AI in search · 26 friends in Quick
Settings · 27 Beta toggles · 28 "Get help" tickets with logs · 29 status
widget · 30 OS achievements.

Updates & safety: 31 OTA daily check, install on shutdown · 32 stable/beta
channels · 33 rollback snapshots (Timeshift) · 34 signed manifests (sha256
now, key later) · 35 ufw on · 36 Ubuntu security updates · 37 full-disk
encryption option · 38 parental controls · 39 shared browser blocklist · 40
Powerwash.

Everyday: 41 Chrome/Chromium + Migood start page · 42 Files + cloud drives · 43
Waydroid (experimental) · 44 GSConnect · 45 screenshot/record · 46 OSK + touch
· 47 battery saver / charge to 80% · 48 CUPS driverless · 49 accessibility ·
50 "Migood OS" Settings page.

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

## Steps

1. Build machine: an Ubuntu 24.04 desktop VM with about 60 GB disk and 8 GB RAM. WSL2 is not enough.
2. The 0.1.0 image in Cubic: run `cubic/customize.sh` (this repo).
3. The OS updater: `overlay/usr/lib/migood-os/update` (this repo).
4. Publish 0.1.0 as a beta release after the owner says OK.
5. Work down the feature list.

## Open questions for the owner

- Which machine/VM builds the image?
- Chromium or Google Chrome?
- Should the Migood app open full screen as "home" on login?
- Who are the first testers?
- What is the server's base URL? It goes in `/etc/migood-os/update.conf`.
