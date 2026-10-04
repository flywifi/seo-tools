# ADR 0073 — The setup wizard and the Scheduling Dashboard bind a fixed port block, without SO_REUSEADDR on Windows

- Status: accepted
- Date: 2026-10-03
- Phase: P101

## Context

The setup wizard bound port 8765 and nothing else (P73). Its publishing OAuth redirect URIs embed
the port (`http://127.0.0.1:<port>/oauth/<platform>/callback`), and a provider compares the
`redirect_uri` with the ones registered for the app, so the port was kept fixed on purpose, with
`CREATOR_OS_WIZARD_PORT` as an escape hatch. On Windows, the operating system can reserve a port
for its own services (Hyper-V and WinNAT keep excluded port ranges, listed by `netsh interface ipv4
show excludedportrange protocol=tcp`); binding a reserved port raises `PermissionError` with
`EACCES` (WinError 10013). The wizard caught every `OSError` alike and said it was "already
running, or port 8765 is in use", which is false for a reserved port, and a Windows user could not
start setup.

Both servers also set `SO_REUSEADDR` (the wizard's `allow_reuse_address = True`; the stock
`http.server.HTTPServer` sets it as well). On POSIX that only lets a restart bind through
`TIME_WAIT`. On Windows a second socket that sets it can bind a port whose first socket set it too,
so two copies of the wizard or the dashboard could share a port without an error. The Scheduling
Dashboard bound 8766 the same way, and two links named 8765 by hand: the dashboard's setup link and
the MCP `launch_setup` result.

## Decision 1: a fixed block per service, walked on EACCES alone

Each service has an ordered block: the wizard 8765, 8775, 8785; the dashboard 8766, 8776, 8786
(`tools/loopback_server.py`). `bind_first` binds the first port of the block and moves to the next
when the bind fails with `EACCES`. On Windows that is a port the system reserves, or one a program
holds on all addresses under another account or exclusively (Microsoft's bind tables), so the note
it prints names both. `EADDRINUSE` stops the walk with the "already running, or port N is in use"
message: the likely holder is a second copy, and starting elsewhere would leave two running. Any other bind error stops it with that error's own
text, and a fully refused block names the ports and the override variable.

The block is fixed, never "the next free port", so the redirect URIs a person registers are known
in advance. All three wizard addresses are registered once: Pinterest accepts several redirect URIs
per app and matches them exactly; TikTok's Login Kit for Desktop accepts up to 10, with `localhost`
or `127.0.0.1` as host, and a wildcard port (`http://127.0.0.1:*/oauth/tiktok/callback` covers the
block and any override); the Instagram screen asks for the URI it shows to be registered with Meta;
a Google Desktop client needs none (`docs/PUBLISHING.md`). `CREATOR_OS_WIZARD_PORT` and the new
`CREATOR_OS_DASHBOARD_PORT` name one port instead of the block. Port 8765 stays first, so an
existing registration keeps working.

## Decision 2: no SO_REUSEADDR on Windows, and no SO_EXCLUSIVEADDRUSE

`loopback_server.RefuseSharedPort` clears `allow_reuse_address` on Windows before the bind and
changes nothing on POSIX. In Microsoft's bind table for Windows Server 2003 and later, two sockets
without options bound to the same specific address give `WSAEADDRINUSE`, so a second copy of either
server is refused with `EADDRINUSE` instead of sharing the port; on Windows a socket without
`SO_REUSEADDR` can still bind a port whose closed connections are in `TIME_WAIT`, which is why
CPython's own `socket.create_server` leaves the option off there. The refusal was executed on Linux
(the `loopback_server` selftest binds a second server on a listening port) and in a manual run on
Windows, where
a second wizard and a second dashboard each exited with the already-running message while the
first kept its port and a closed wizard's port was bound again at once.

`SO_EXCLUSIVEADDRUSE` was considered and not used. For a socket bound to one specific address, its
row in Microsoft's tables matches the row for no options, in the same-account and the
different-account tables, so it would refuse the same binds; and a listening socket with it that
accepted a connection blocks a later exclusive bind of the port until that connection ends, so
closing and restarting the wizard could read as "already running".

## Decision 3: the links follow the port each server bound

The wizard records the port it bound, with the launch id `launch_setup` gave it, in the ignored
`creator-os-wizard-port.local.json`; the dashboard records its own in
`creator-os-dashboard-port.local.json`. The dashboard serves the wizard's address at
`GET /api/wizard-url` (a file read; its GET routes make no network call, which its selftest checks
for every route it serves, with a record present), and its setup button opens the tab first and
then points it there. `launch_setup` waits a few seconds for a record carrying its launch id and
reports that address, naming the block's other ports when it could not confirm one; the publishing
plan's `dashboard_url` reads the dashboard's record. The wizard's same-origin check reads the bound
port at call time; it had captured 8765 as a default argument, which would have refused the
wizard's own pages on another port.

At start, the wizard asks the port last recorded what answers there (`probe`, which looks for the
title on the wizard's home page, within about a second in all). It reports a wizard that answers,
or a connection that is accepted without an answer in time (the wizard serves one request at a
time, so a busy copy looks like this), as already running; the bind alone would not see a copy
that moved along the block. Another program answering there, or nothing listening, does not stop
it. A clean shutdown removes the record when it still names that wizard (its port and launch id),
and the dashboard removes its own record when it still names its port.

## Decision 4: a read timeout on each request

Both servers handle one request at a time (`socketserver.TCPServer`), and browsers open spare
connections ahead of use. One that stays idle held the server: pages, and the wizard's Quit,
waited until the browser closed it. Each request handler sets `timeout` to
`loopback_server.REQUEST_TIMEOUT` (3 seconds); socketserver applies it to the connection and
`http.server` closes a connection whose read or write times out, so the next request is answered.
Each idle connection ahead of a request still delays it by up to that long (two spare
connections, about 6 seconds). The wizard's form reader re-raises the read timeout, so a body that
stops arriving closes the connection rather than reading as an empty form. A threading server was
not used: the wizard's start-up `probe` reads a copy that accepts a
connection without answering as busy, and threads would run the handlers, which share module
state, at the same time.

## Consequences

- A Windows computer that reserves 8765 runs the wizard on 8775 (or 8785) and says why, instead
  of a false "already running".
- A person who uses TikTok, Pinterest or Instagram publishing registers the extra redirect URIs
  (TikTok can take one wildcard entry). Until they do, a wizard that had to move off 8765 cannot
  complete those connections.
- A program under another account that holds a block port is walked past like a reserved port,
  and the note says it may be either.
- The walk, the bind policy and the port records are one implementation with one selftest
  (`tools/loopback_server.py --selftest`), used by both servers; their committed mutation cases
  live in `tools/file_hash.py`.
- The dashboard's own record is read by the MCP tools; after a dashboard that did not shut down
  cleanly, they name its last port until the next start. The workflow script that names the
  dashboard keeps 8766 and tells the reader to use the address the dashboard printed.

```sources
[
  {"id": "ms-winsock-reuseaddr-exclusiveaddruse", "name": "Microsoft Learn - Using SO_REUSEADDR and SO_EXCLUSIVEADDRUSE", "url": "https://learn.microsoft.com/en-us/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse", "category": "os-platform", "tier": "T1", "extraction_hint": "Windows Server 2003 and later bind tables: two binds with no options on the same specific address give WSAEADDRINUSE; the SO_EXCLUSIVEADDRUSE row for a specific address matches the no-options row in the same-account and different-account tables; a listening SO_EXCLUSIVEADDRUSE socket that accepted a connection blocks a later SO_EXCLUSIVEADDRUSE bind of the port until the connection becomes inactive."},
  {"id": "cpython-socket-create-server", "name": "CPython Lib/socket.py - create_server", "url": "https://github.com/python/cpython/blob/3.13/Lib/socket.py", "category": "software-dependency", "tier": "T1", "extraction_hint": "create_server leaves SO_REUSEADDR off on Windows: bind() succeeds even when a previous closed socket on the same address is still in TIME_WAIT, and the option would let another socket bind the same address."},
  {"id": "tiktok-login-kit-desktop", "url": "https://developers.tiktok.com/doc/login-kit-desktop/"},
  {"id": "pinterest-connect-app", "url": "https://developers.pinterest.com/docs/getting-started/connect-app/"}
]
```
