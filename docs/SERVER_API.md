# Migood server endpoints the OS uses

For the Migood server session. The OS sends `Authorization: Bearer <token>`
(from `POST /api/auth/token`) and tries the servers in `/etc/migood-os/update.conf`
in order: main site first, then backups.

## Used today

| Endpoint | Used by | What the OS expects |
|---|---|---|
| `POST /api/auth/token` `{username, password}` | setup sign-in | `{token}` (or `access_token`), else `{error}` |
| `GET /api/me` | setup, profile sync, server "Test" | `username`, `displayName`, `ageBand` (`junior`/`teen`/…), `friends`; 401 `{"error":"Not logged in"}` when no token |
| `GET /cdn/pfps/<username>.png` | account picture | PNG, public |
| `GET /api/os/updates?from=&channel=` | updater | releases oldest first: `{version, notes, files:[{name, sha256, size}]}`; a bare list or `{releases:[…]}` |
| `GET /api/os/files/<name>` | updater | the file, `Range` supported |
| `POST /api/os/checkin` `{device, version, channel}` | updater | any 2xx |
| `POST /api/support/open` `{subject, message, category}` | Settings → Get help | any 2xx, else `{error}` |
| `POST /api/ai/chat` `{mode:"normal", messages, private:true}` | Migood AI window / search | `{reply, water, waterMax}`, else `{error}` |
| `/homes.html?section=email` | Migood Mail | the web page |

## Still needed (OS side is ready to call them)

| Feature | What the OS needs |
|---|---|
| Friends in Quick Settings (26) | friends with online/playing state, e.g. `GET /api/friends/online` → `[{username, displayName, online, playing}]` |
| Shop points (Plan 6) | nothing from the OS: the server counts playtime / Lives itself. Optional: `GET /api/shop/points` to show the balance in the top bar |
| OS achievements (30) | `POST /api/os/achievement {id}` for first boot, first game…; the server decides if it counts |
| Seasonal wallpapers (4) | `GET /api/os/wallpapers` → `[{name, url, season}]`, respecting the Seasonal toggle |
| Status widget (29) | `GET /api/status` → `{ok, message}` |
| Cloud saves (20) | how `/api/appsaves` should be called for non-Migood (PC) games, if at all |
| Parental controls (38) / blocklist (39) | the account's rules + the shared blocklist |
