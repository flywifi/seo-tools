"""Loopback HTTP servers for the setup wizard and the Scheduling Dashboard (P101).

Each service has a fixed, ordered port block. bind_first() binds the first port of the block,
moving to the next when the bind is refused with EACCES: on Windows, a port the system reserves
(Hyper-V and WinNAT keep excluded ranges; `netsh interface ipv4 show excludedportrange
protocol=tcp` lists them), or one a program holds on all addresses under another account or
exclusively (Microsoft's bind tables). A port held another way (EADDRINUSE) stops the walk, since a
second copy of the service is the likely holder and starting elsewhere would leave two running. The block is fixed, never "the next free
port", because the wizard's OAuth redirect URIs embed the port and each address is registered with
a provider in advance.

RefuseSharedPort makes a second server on a listening port fail with EADDRINUSE on Windows too.
There, SO_REUSEADDR (which socketserver sets when allow_reuse_address is true) lets a second socket
bind a port that is already listening, and a socket without it can rebind a port whose closed
connections are still in TIME_WAIT, so it is cleared, as CPython's socket.create_server does on
Windows. On POSIX SO_REUSEADDR only lets a restart bind through TIME_WAIT, so it stays.
SO_EXCLUSIVEADDRUSE is not used: for a socket bound to one address it refuses the same binds
(Microsoft's bind tables) and it blocks a restart until the closed server's connections end.

The wizard records the port it bound with port_record() in WIZARD_PORT_FILE and the dashboard in
DASHBOARD_PORT_FILE (both ignored by git); the dashboard's setup link and the MCP tools read them
with read_port() (launched_wizard_url, launch_note, dashboard_url), so neither probes the network
to find the other. probe() asks one port what answers there, for the wizard's own start-up check.

Both servers handle one request at a time, so their handlers set REQUEST_TIMEOUT: a browser opens
spare connections ahead of use and may leave one idle, and without a read timeout the server would
wait on that connection, unable to answer anything else, until the browser closed it.

    python3 tools/loopback_server.py --selftest
"""
from __future__ import annotations

import errno
import json
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WIZARD_BLOCK = (8765, 8775, 8785)
DASHBOARD_BLOCK = (8766, 8776, 8786)
WIZARD_PORT_FILE = ROOT / "creator-os-wizard-port.local.json"
DASHBOARD_PORT_FILE = ROOT / "creator-os-dashboard-port.local.json"
# The <title> of a page the wizard renders through wizard._page (its home page among them) ends
# with this, so probe() can tell the wizard apart from another program on the same port.
WIZARD_TITLE_MARK = b" - Creator OS Setup</title>"
# Seconds either server's request handler waits on a read or a write (socketserver applies it to
# the connection; http.server closes a connection whose read or write times out).
REQUEST_TIMEOUT = 3


class RefuseSharedPort:
    """Mixin for a socketserver.TCPServer subclass; list it before the server class."""

    def server_bind(self):
        if os.name == "nt":
            self.allow_reuse_address = False
        super().server_bind()


class BindRefused(Exception):
    """Why bind_first() bound nothing. kind is "in_use" (EADDRINUSE at port), "reserved" (the OS
    reserves every port tried) or "error" (another OSError at port, kept in .error); tried lists
    the reserved ports skipped before it. The wizard also raises it as "recorded" when the port its
    record names answers as a wizard, or accepts without answering in time."""

    def __init__(self, kind, port, tried, error=None):
        super().__init__(f"{kind} at port {port}")
        self.kind, self.port, self.tried, self.error = kind, port, list(tried), error


def ports(env_var, block, environ=None, note=print):
    """The ports to try: the one port env_var names when it holds 1024 to 65535, else block (with a
    printed note when env_var is set but unusable)."""
    raw = (os.environ if environ is None else environ).get(env_var)
    if not raw:
        return tuple(block)
    listed = ", ".join(str(p) for p in block)
    try:
        val = int(raw)
    except ValueError:
        note(f"[{env_var}] {raw!r} is not a number; trying {listed}.")
        return tuple(block)
    if not 1024 <= val <= 65535:
        note(f"[{env_var}] {val} is out of range (1024 to 65535); trying {listed}.")
        return tuple(block)
    return (val,)


def bind_first(block, factory):
    """(server, port, reserved): factory(port) for the first port of block that binds, and the
    ports skipped before it because the OS reserves them. Raises BindRefused otherwise."""
    reserved = []
    for port in block:
        try:
            return factory(port), port, reserved
        except OSError as exc:
            if exc.errno == errno.EACCES:
                reserved.append(port)
                continue
            if exc.errno == errno.EADDRINUSE:
                raise BindRefused("in_use", port, reserved, exc) from exc
            raise BindRefused("error", port, reserved, exc) from exc
    raise BindRefused("reserved", reserved[-1] if reserved else None, reserved)


def refusal_lines(exc, name, env_var):
    """What to print when bind_first() raised exc for the service called name."""
    if exc.kind == "in_use":
        return [f"{name} is already running, or port {exc.port} is in use.",
                f"Open http://localhost:{exc.port}/ in your browser, or close the other window "
                "and try again."]
    if exc.kind == "recorded":
        return [f"{name} is already running at http://localhost:{exc.port}/ (the port it last "
                "recorded), or another program there accepted the connection and did not answer.",
                f"Open that address, or close the other window; if no copy of {name} is open, delete "
                f"{WIZARD_PORT_FILE.name} and start it again."]
    if exc.kind == "reserved":
        listed = ", ".join(str(p) for p in exc.tried)
        return [f"This computer refused port {listed} to {name} (it reserves it for its own "
                "network services, or a program holds it on all addresses under another account "
                "or exclusively). On Windows, `netsh interface ipv4 show excludedportrange "
                "protocol=tcp` lists the reserved ranges.",
                f"Set {env_var} to a free port from 1024 to 65535 and start it again."]
    return [f"{name} could not listen on port {exc.port}: {exc.error}"]


def reserved_note(reserved, port, name):
    """What to print when bind_first() skipped refused ports before binding port."""
    listed = ", ".join(str(p) for p in reserved)
    return (f"Port {listed} was refused (reserved by this computer's network configuration, or held "
            f"on all addresses by a program under another account or exclusively); {name} is "
            f"using port {port}.")


def port_record(port, launch_id=None) -> str:
    """The text a server writes to its port file (WIZARD_PORT_FILE, DASHBOARD_PORT_FILE) after it
    binds port."""
    return json.dumps({"port": port, "launch_id": launch_id}) + "\n"


def read_port(path=None):
    """(port, launch_id) from a port_record() file (by default WIZARD_PORT_FILE, read at call
    time), or (None, None) when it is missing or bad."""
    try:
        doc = json.loads(Path(WIZARD_PORT_FILE if path is None else path).read_text(encoding="utf-8"))
        port = doc.get("port")
        if isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535:
            return port, doc.get("launch_id")
    except (OSError, ValueError, AttributeError):
        pass
    return None, None


def probe(port, mark=WIZARD_TITLE_MARK, timeout=1.0) -> str:
    """What answers GET / on 127.0.0.1:port within about `timeout` seconds in all: "wizard" (a
    reply carrying mark), "other" (a reply without it, or a connection closed or reset), "silent"
    (the connection was accepted but mark did not arrive in time; a single-threaded wizard busy
    with another request looks like this) or "closed" (nothing accepts the connection)."""
    import time
    deadline = time.monotonic() + timeout
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    except OSError:
        return "closed"
    try:
        sock.sendall(b"GET / HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n")
        got = b""
        while len(got) < 262144:
            left = deadline - time.monotonic()
            if left <= 0:
                return "silent"
            sock.settimeout(left)
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                return "silent"
            if not chunk:
                return "other"
            got += chunk
            if mark in got:
                return "wizard"
        return "other"
    except OSError:
        return "other"
    finally:
        sock.close()


def launched_wizard_url(proc, launch_id, wait=6.0, sleep=None, read=None) -> tuple:
    """(url, confirmed) for the wizard the MCP launch_setup tool started. The wizard records the
    port of its block it bound together with the launch id it was given (port_record); this polls
    that record for up to `wait` seconds. When the process exits first (another wizard already
    holds the port) or nothing arrives in time, the url is the port last recorded, else the first
    port the wizard tries, and confirmed is False."""
    import time
    sleep = time.sleep if sleep is None else sleep
    read = read_port if read is None else read
    for _ in range(max(1, int(wait / 0.2))):
        port, recorded_id = read()
        if port is not None and recorded_id == launch_id:
            return f"http://localhost:{port}/", True
        if proc.poll() is not None:
            break
        sleep(0.2)
    port, _ = read()
    if port is None:
        port = ports("CREATOR_OS_WIZARD_PORT", WIZARD_BLOCK, note=lambda _msg: None)[0]
    return f"http://localhost:{port}/", False


def launch_note(url, confirmed) -> str:
    """launch_setup's note for the url launched_wizard_url returned: when the address is not
    confirmed, the other ports the wizard may be on."""
    if confirmed:
        return "The setup wizard is opening in your web browser. If it does not open, visit the URL above."
    others = [str(p) for p in ports("CREATOR_OS_WIZARD_PORT", WIZARD_BLOCK, note=lambda _msg: None)
              if f"localhost:{p}/" not in url]
    return ("The wizard has not reported its address (one may already be running, or it is still "
            "starting); try the URL above" + (f", then port {', '.join(others)} on the same computer"
                                              if others else "") + ".")


def dashboard_url(read=None) -> str:
    """The Scheduling Dashboard's address: the port it recorded when it bound, else the first port
    it tries (CREATOR_OS_DASHBOARD_PORT when set, else 8766)."""
    port, _ = read() if read is not None else read_port(DASHBOARD_PORT_FILE)
    if port is None:
        port = ports("CREATOR_OS_DASHBOARD_PORT", DASHBOARD_BLOCK, note=lambda _msg: None)[0]
    return f"http://localhost:{port}"


# --- selftest: everything below is test code ---

def _selftest_idle_reply(make_server, path, wait=3.0) -> tuple:
    """For the two servers' selftests: serve make_server(("127.0.0.1", 0)) on a thread, hold one
    connection open that sends nothing (a browser's spare connection), then ask for path. Returns
    the reply's first bytes and the seconds it took, or (b"", seconds) when nothing arrived within
    `wait` seconds."""
    import threading
    import time
    srv = make_server(("127.0.0.1", 0))
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    port = srv.server_address[1]
    idle = socket.create_connection(("127.0.0.1", port))
    asked = socket.create_connection(("127.0.0.1", port), timeout=wait)
    began = time.monotonic()
    try:
        asked.sendall(f"GET {path} HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n".encode("ascii"))
        try:
            got = asked.recv(64)
        except socket.timeout:
            got = b""
        return got, time.monotonic() - began
    finally:
        asked.close()
        idle.close()   # first, so a server still waiting on it can stop
        stopper = threading.Thread(target=srv.shutdown, daemon=True)
        stopper.start()
        stopper.join(5.0)
        srv.server_close()


def _selftest_applied_timeout(handler_class):
    """For the two servers' selftests: the timeout handler_class's own setup() applies to a
    connection (one end of a socket pair), without serving a request."""
    near, far = socket.socketpair()
    handler = handler_class.__new__(handler_class)
    handler.request = near
    try:
        handler_class.setup(handler)
        return near.gettimeout()
    finally:
        for stream in ("rfile", "wfile"):
            if hasattr(handler, stream):
                getattr(handler, stream).close()
        near.close()
        far.close()


def selftest() -> int:
    import socketserver
    import tempfile

    checks = []

    def ok(name, cond):
        checks.append((name, bool(cond)))
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")

    def factory(errnos):
        calls = []

        def make(port):
            calls.append(port)
            code = errnos.get(port)
            if code is None:
                return ("server", port)
            raise OSError(code, os.strerror(code))
        return make, calls

    def refused(block, make):
        try:
            bind_first(block, make)
        except BindRefused as exc:
            return exc.kind, exc.port, exc.tried, exc.error
        return None

    block = WIZARD_BLOCK
    make, calls = factory({8765: errno.EACCES})
    server, port, reserved = bind_first(block, make)
    ok("a reserved port (EACCES) moves the walk to the next port of the block",
       server == ("server", 8775) and port == 8775 and reserved == [8765] and calls == [8765, 8775])
    make, calls = factory({})
    ok("a free first port is bound with nothing skipped",
       bind_first(block, make) == (("server", 8765), 8765, []) and calls == [8765])
    make, calls = factory({8765: errno.EADDRINUSE})
    got = refused(block, make)
    ok("a port in use (EADDRINUSE) stops the walk there",
       got is not None and got[:3] == ("in_use", 8765, []) and calls == [8765])
    make, calls = factory({8765: errno.EACCES, 8775: errno.EADDRINUSE})
    got = refused(block, make)
    ok("a port in use after a reserved one stops the walk at the port in use",
       got is not None and got[:3] == ("in_use", 8775, [8765]) and calls == [8765, 8775])
    make, calls = factory({p: errno.EACCES for p in block})
    got = refused(block, make)
    ok("when every port of the block is reserved the walk refuses and lists them",
       got is not None and got[:3] == ("reserved", 8785, [8765, 8775, 8785]) and calls == list(block))
    make, calls = factory({8765: errno.EADDRNOTAVAIL})
    got = refused(block, make)
    ok("another bind error stops the walk and keeps the error",
       got is not None and got[:3] == ("error", 8765, []) and calls == [8765]
       and isinstance(got[3], OSError) and got[3].errno == errno.EADDRNOTAVAIL)

    in_use = refusal_lines(BindRefused("in_use", 8765, []), "Creator OS Setup", "X_PORT")
    ok("a port in use is reported as another copy running, with its address",
       in_use == ["Creator OS Setup is already running, or port 8765 is in use.",
                  "Open http://localhost:8765/ in your browser, or close the other window and "
                  "try again."])
    res = " ".join(refusal_lines(BindRefused("reserved", 8785, [8765, 8775, 8785]), "S", "X_PORT"))
    ok("a fully reserved block is reported as reserved, never as already running, with the override",
       "8765, 8775, 8785" in res and "already running" not in res and "X_PORT" in res)
    rec = " ".join(refusal_lines(BindRefused("recorded", 8785, []), "S", "X_PORT"))
    ok("a refusal from the recorded port names its address and the record file to delete",
       "http://localhost:8785/" in rec and WIZARD_PORT_FILE.name in rec)
    err = refusal_lines(BindRefused("error", 8765, [], OSError(errno.EADDRNOTAVAIL, "nope")), "S", "X")
    ok("another bind error is reported with its own text", len(err) == 1 and "nope" in err[0])
    note = reserved_note([8765], 8775, "Creator OS Setup")
    ok("a walk past a reserved port names the reserved port and the one in use",
       "8765" in note and "8775" in note and "already running" not in note)

    notes = []
    ok("no override: the whole block is tried",
       ports("X_PORT", block, environ={}, note=notes.append) == block and not notes)
    ok("an override in range is tried alone",
       ports("X_PORT", block, environ={"X_PORT": "8790"}, note=notes.append) == (8790,) and not notes)
    ok("an override that is not a number falls back to the block with a note",
       ports("X_PORT", block, environ={"X_PORT": "abc"}, note=notes.append) == block and len(notes) == 1)
    ok("an override out of range falls back to the block with a note",
       ports("X_PORT", block, environ={"X_PORT": "80"}, note=notes.append) == block and len(notes) == 2)
    ok("an override above 65535 falls back to the block with a note",
       ports("X_PORT", block, environ={"X_PORT": "65536"}, note=notes.append) == block and len(notes) == 3)
    ok("the override bounds 1024 and 65535 are accepted",
       ports("X_PORT", block, environ={"X_PORT": "1024"}, note=notes.append) == (1024,)
       and ports("X_PORT", block, environ={"X_PORT": "65535"}, note=notes.append) == (65535,)
       and len(notes) == 3)

    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "port.local.json"
        ok("a missing port file reads as nothing", read_port(f) == (None, None))
        f.write_text(port_record(8775, "abc"), encoding="utf-8")
        ok("a port record reads back with its launch id", read_port(f) == (8775, "abc"))
        for bad in ("not json", '{"port": "8775"}', '{"port": 0}', '{"port": 65536}',
                    '{"port": true}', "[8775]"):
            f.write_text(bad, encoding="utf-8")
            if read_port(f) != (None, None):
                ok(f"a bad port file reads as nothing: {bad}", False)
                break
        else:
            ok("a bad port file (not JSON, a string, 0, 65536, a boolean, a list) reads as nothing", True)

    # Real sockets: a second server cannot share a listening port, the walk reports it in use,
    # and a port can be bound again once its server is closed.
    class _Server(RefuseSharedPort, socketserver.TCPServer):
        allow_reuse_address = True

    first = _Server(("127.0.0.1", 0), socketserver.BaseRequestHandler)
    busy = first.server_address[1]
    try:
        try:
            _Server(("127.0.0.1", busy), socketserver.BaseRequestHandler).server_close()
            second = "bound"
        except OSError as exc:
            second = exc.errno
        ok("a second server on a listening port is refused with EADDRINUSE", second == errno.EADDRINUSE)
        got = refused((busy,), lambda p: _Server(("127.0.0.1", p), socketserver.BaseRequestHandler))
        ok("the walk reports a listening port as in use", got is not None and got[:2] == ("in_use", busy))
    finally:
        first.server_close()
    try:
        _Server(("127.0.0.1", busy), socketserver.BaseRequestHandler).server_close()
        again = True
    except OSError:
        again = False
    ok("a port is bound again after its server closed", again)

    # The Windows branch, with the module's os stood in for: SO_REUSEADDR is cleared before the
    # bind and no other socket option is set; under POSIX it stays.
    class _AsOs:
        def __init__(self, name):
            self.name = name

        def __getattr__(self, attr):
            return getattr(real_os, attr)

    class _Recorder:
        def __init__(self):
            self.calls = []

        def setsockopt(self, *args):
            self.calls.append(args)

    class _Base:
        allow_reuse_address = True

        def server_bind(self):
            self.reuse_at_bind = self.allow_reuse_address

    class _Probe(RefuseSharedPort, _Base):
        pass

    g, real_os = globals(), os
    seen = {}
    for name in ("nt", "posix"):
        candidate = _Probe()
        candidate.socket = _Recorder()
        g["os"] = _AsOs(name)
        try:
            candidate.server_bind()
        finally:
            g["os"] = real_os
        seen[name] = (candidate.reuse_at_bind, candidate.socket.calls)
    ok("on Windows a server binds without SO_REUSEADDR and sets no other option", seen["nt"] == (False, []))
    ok("on POSIX a server keeps SO_REUSEADDR and sets no other option", seen["posix"] == (True, []))

    # probe(): what answers on a port, within about its timeout in all. Each probe runs in a thread
    # with a time limit, so a probe that would wait forever fails its check instead of hanging.
    import http.server
    import threading
    import time

    def serving(body):
        class _H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), _H)
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        return srv

    def raw(reply_after_request):
        lst = socket.socket()
        lst.bind(("127.0.0.1", 0))
        lst.listen(4)
        if reply_after_request is not None:
            def serve():
                try:
                    conn, _ = lst.accept()
                    conn.recv(4096)
                    reply_after_request(conn)
                    conn.close()
                except OSError:
                    pass
            threading.Thread(target=serve, daemon=True).start()
        return lst

    def guarded(port, timeout):
        out = {}
        worker = threading.Thread(target=lambda: out.setdefault("v", probe(port, timeout=timeout)),
                                  daemon=True)
        began = time.monotonic()
        worker.start()
        worker.join(5.0)
        return out.get("v", "hung"), time.monotonic() - began

    def drip(conn):
        conn.sendall(b"HTTP/1.0 200 OK\r\n\r\n")
        for _ in range(40):
            time.sleep(0.1)
            conn.sendall(b"x")

    def reset(conn):   # close with a zero linger time: the peer sees a reset
        conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, __import__("struct").pack("ii", 1, 0))

    def mark_then_hang(conn):
        conn.sendall(b"HTTP/1.0 200 OK\r\nContent-Length: 100000\r\n\r\n<title>Home" + WIZARD_TITLE_MARK)
        time.sleep(2.0)

    wizard_like = serving(b"<title>Home" + WIZARD_TITLE_MARK)
    other = serving(b"<title>Something else</title>")
    silent, dripping, hanging, resetting = raw(None), raw(drip), raw(mark_then_hang), raw(reset)
    try:
        closed = _Server(("127.0.0.1", 0), socketserver.BaseRequestHandler)
        closed_port = closed.server_address[1]
        closed.server_close()
        ok("probe() finds the wizard's title, another server and a closed port",
           guarded(wizard_like.server_address[1], 1.0)[0] == "wizard"
           and guarded(other.server_address[1], 1.0)[0] == "other"
           and guarded(closed_port, 1.0)[0] == "closed")
        got, took = guarded(silent.getsockname()[1], 0.2)
        ok("a port that accepts the connection and never answers is silent, within about the timeout",
           got == "silent" and took < 1.0)
        got, took = guarded(dripping.getsockname()[1], 0.3)
        ok("a reply that trickles in without the mark is silent at the timeout, not later",
           got == "silent" and took < 1.0)
        got, took = guarded(hanging.getsockname()[1], 1.0)
        ok("a reply that carries the mark and then stalls is the wizard, without waiting for its end",
           got == "wizard" and took < 0.9)
        ok("a connection reset after the accept is another program, not a busy wizard",
           guarded(resetting.getsockname()[1], 1.0)[0] == "other")
        real_connect = socket.create_connection

        def _timed_out(*args, **kwargs):
            raise TimeoutError("connect timed out")
        socket.create_connection = _timed_out
        try:
            timed_out = probe(8765, timeout=0.2)
        finally:
            socket.create_connection = real_connect
        ok("a connect that times out is closed, not a busy wizard", timed_out == "closed")

        def _refused(*args, **kwargs):
            raise ConnectionRefusedError("connection refused")
        socket.create_connection = _refused
        try:
            refused = probe(8765, timeout=0.2)
        except OSError as exc:
            refused = repr(exc)
        finally:
            socket.create_connection = real_connect
        # Stood in for: on Windows a refused loopback connect is retried and outlasts a 1 s timeout.
        ok("a refused connect is closed", refused == "closed")
        ok("REQUEST_TIMEOUT is the 3 seconds the docs state", REQUEST_TIMEOUT == 3)
    finally:
        for srv in (wizard_like, other):
            srv.shutdown()
            srv.server_close()
        for lst in (silent, dripping, hanging, resetting):
            lst.close()

    # launched_wizard_url / launch_note / dashboard_url: the addresses the MCP tools report.
    class _Proc:
        def __init__(self, exits_after):
            self.polls, self.exits_after = 0, exits_after

        def poll(self):
            self.polls += 1
            return 0 if self.polls > self.exits_after else None

    def _reads(*answers):
        seq = list(answers)
        return lambda: seq.pop(0) if len(seq) > 1 else seq[0]

    naps = []
    saved_env = {k: os.environ.get(k) for k in ("CREATOR_OS_WIZARD_PORT", "CREATOR_OS_DASHBOARD_PORT")}
    saved_dash = DASHBOARD_PORT_FILE
    try:
        for key in saved_env:
            os.environ.pop(key, None)
        got = launched_wizard_url(_Proc(99), "L1", sleep=naps.append,
                                  read=_reads((8765, "old"), (8765, "old"), (8775, "L1")))
        ok("launch_setup's address is the port the started wizard recorded with its launch id",
           got == ("http://localhost:8775/", True) and naps == [0.2, 0.2])
        del naps[:]
        ok("a wizard that exits at once (one already running) is reported unconfirmed at the port "
           "last recorded, without waiting",
           launched_wizard_url(_Proc(0), "L2", sleep=naps.append, read=_reads((8775, "old")))
           == ("http://localhost:8775/", False) and naps == [])
        got = launched_wizard_url(_Proc(99), "L3", wait=1.0, sleep=naps.append, read=_reads((None, None)))
        ok("with nothing recorded the address is port 8765, unconfirmed, after a bounded wait",
           got == ("http://localhost:8765/", False) and naps == [0.2] * 5)
        note = launch_note("http://localhost:8775/", False)
        ok("an unconfirmed launch note names the other ports of the block, not the one shown",
           "8765" in note and "8785" in note and "8775" not in note
           and "8775" not in launch_note("http://localhost:8775/", True)
           and "visit the URL above" in launch_note("http://localhost:8775/", True))
        with tempfile.TemporaryDirectory() as td:
            g["DASHBOARD_PORT_FILE"] = Path(td) / "dashboard-port.local.json"
            ok("with no dashboard record the dashboard address is port 8766", dashboard_url() == "http://localhost:8766")
            g["DASHBOARD_PORT_FILE"].write_text(port_record(8776), encoding="utf-8")
            ok("the dashboard address is the port the dashboard recorded", dashboard_url() == "http://localhost:8776")
            g["DASHBOARD_PORT_FILE"].unlink()
            os.environ.update(CREATOR_OS_WIZARD_PORT="9123", CREATOR_OS_DASHBOARD_PORT="9124")
            ok("with nothing recorded, the wizard and dashboard addresses use their overrides",
               launched_wizard_url(_Proc(0), "L5", sleep=naps.append, read=_reads((None, None)))
               == ("http://localhost:9123/", False)
               and dashboard_url() == "http://localhost:9124"
               and "8765" not in launch_note("http://localhost:9123/", False))
    finally:
        g["DASHBOARD_PORT_FILE"] = saved_dash
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    failed = [n for n, c in checks if not c]
    print(f"loopback_server selftest: {len(checks) - len(failed)}/{len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(selftest())
    print(__doc__)
