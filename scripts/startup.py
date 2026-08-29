"""
startup.py - brings up the go-ios tunnel, WebDriverAgent, the 8100 port
forward, and Appium, then shuts them all down again.

Same order and same retry logic as startup.bat, minus the PowerShell
wrappers, PID files and Tee-Object.

Press Enter or Ctrl+C at ANY point to terminate. Everything started so
far gets killed on the way out.

The tunnel and WDA show their live output in a fixed-height block that
updates in place. On success the block is wiped and replaced with one
status line. On failure it is left on screen. Full untruncated output is
always in temp/<name>_log.txt.

Appium gets its own PowerShell window so you can watch it separately. It
is still killed with everything else on exit.

Run from a terminal that has admin rights ("ios tunnel start" needs them):
    python startup.py
"""

import re
import shutil
import subprocess
import sys
import threading
import time
import state
from collections import deque, namedtuple
from pathlib import Path

# ---------------------------------------------------------------- settings

if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).resolve().parent
else:
    HERE = Path(__file__).resolve().parent
TEMP = HERE / "temp"

# None = ask go-ios which device is attached. Put a UDID string here to force one.
UDID = "00008140-001130441A2A801C"

WDA_BUNDLE = "com.lithum.WebDriverAgent.xctrunner"
WDA_XCTEST = "WebDriverAgentRunner.xctest"

# The line go-ios prints once the tunnel is actually up.
TUNNEL_READY_MARKER = "Removed orphaned adapter"

# Matches  "authorized":true  in the runwda log, however it is spaced/quoted.
AUTHORIZED_RE = re.compile(r'"?authorized"?\s*[:=]\s*"?(true|false)', re.IGNORECASE)

# Modern (8-16 hex) and legacy (40 hex) iOS device identifiers.
UDID_RE = re.compile(r"\b(?:[0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}|[0-9a-f]{40})\b")

TUNNEL_ATTEMPTS = 2          # whole-tunnel restarts before giving up
TUNNEL_POLLS = 5             # log checks per attempt
TUNNEL_POLL_SECONDS = 2

WDA_ATTEMPTS = 3
WDA_SETTLE_SECONDS = 5       # wait before reading the runwda log

LOG_WINDOW_LINES = 8         # how many live log lines to show at once

# ------------------------------------------------------------ abort handling

STOP = threading.Event()      # set by Enter, Ctrl+C, or a fatal error


class Aborted(Exception):
    """Raised out of wait() so any step unwinds straight to cleanup."""


def watch_for_enter():
    """Background thread: first line typed on stdin sets the STOP flag."""
    if sys.stdin and sys.stdin.isatty():
        try:
            sys.stdin.readline()
        except Exception:
            return
        STOP.set()


def wait(seconds):
    """Sleep, but bail out immediately if STOP gets set.

    Sleeps in 0.25s slices so Enter is noticed straight away instead of at
    the end of a 5 second block.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if STOP.wait(min(0.25, deadline - time.monotonic())):
            raise Aborted()
    if STOP.is_set():
        raise Aborted()


# ------------------------------------------------------- live log window

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")   # strips colour codes go-ios may emit
ANSI_OK = True                                   # set False if the console can't do it


def enable_ansi():
    """Turn on ANSI escape handling in the Windows console.

    Escape codes are how the cursor gets moved back up to overwrite lines.
    Windows 10+ supports them but the flag is off by default for older apps.
    """
    global ANSI_OK
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # -11 is STD_OUTPUT_HANDLE, 0x0004 is ENABLE_VIRTUAL_TERMINAL_PROCESSING
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            raise OSError
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        ANSI_OK = False


class LiveTail:
    """A block of the last N log lines that redraws itself in place.

    add()   - push a new line into the block and redraw it
    wipe()  - erase the block entirely (use when the step succeeded)
    keep()  - stop touching the block, leave it on screen (use on failure)
    """

    def __init__(self, height=LOG_WINDOW_LINES):
        self.height = height
        self.window = deque(maxlen=height)
        self.on_screen = 0          # rows this block currently occupies
        self.closed = False
        self.lock = threading.Lock()

    def _fit(self, line):
        """Trim a line to one console row.

        This matters: if a line wrapped onto two rows, the cursor-up count
        would be wrong and the redraw would eat unrelated output.
        """
        line = ANSI_RE.sub("", line).expandtabs(4).rstrip()
        width = shutil.get_terminal_size(fallback=(100, 30)).columns - 1
        return line[:width]

    def add(self, line):
        with self.lock:
            if self.closed:
                return
            self.window.append(self._fit(line))
            if not ANSI_OK:
                sys.stdout.write(self.window[-1] + "\n")
                sys.stdout.flush()
                return
            out = [f"\x1b[{self.on_screen}A"] if self.on_screen else []
            for entry in self.window:
                out.append("\x1b[2K" + entry + "\n")   # 2K = erase whole row
            sys.stdout.write("".join(out))
            sys.stdout.flush()
            self.on_screen = len(self.window)

    def wipe(self):
        with self.lock:
            self.closed = True
            if not ANSI_OK or not self.on_screen:
                return
            # up N rows, blank each one, then back up to the top of the block
            sys.stdout.write(f"\x1b[{self.on_screen}A"
                             + "\x1b[2K\n" * self.on_screen
                             + f"\x1b[{self.on_screen}A")
            sys.stdout.flush()
            self.on_screen = 0

    def keep(self):
        with self.lock:
            self.closed = True
            self.on_screen = 0


# ------------------------------------------------------------ process plumbing

Child = namedtuple("Child", "proc handle thread tail")

RUNNING = {}      # name -> Child

NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

def resolve(program):
    """Find a program on PATH and return its full path.

    shutil.which handles the Windows PATHEXT rules, so "appium" resolves to
    appium.cmd and "ios" resolves to ios.exe without a shell involved.
    """
    path = shutil.which(program)
    if path is None:
        sys.exit(f"'{program}' is not on PATH - install it or fix PATH, then rerun.")
    return path


def _pump(proc, handle, tail, sink=None):
    """Read the child's output line by line: into the log file and onto screen."""
    for line in proc.stdout:
        try:
            handle.write(line)
            handle.flush()
        except ValueError:      # handle already closed during shutdown
            pass
        if sink is not None:
            sink(ANSI_RE.sub("", line))
        else:
            tail.add(line)


def launch(name, args, live=False, sink=None):
    """Start a child process. Output goes to temp/<name>_log.txt.

    live=True also streams it into a LiveTail block on screen.
    Returns (log_path, tail_or_None).
    """
    log_path = TEMP / f"{name}_log.txt"
    handle = open(log_path, "w", encoding="utf-8", errors="replace")

    if live:
        proc = subprocess.Popen(
            [resolve(args[0])] + args[1:],
            cwd=str(HERE),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=NO_WINDOW
        )
        tail = LiveTail() if sink is None else None
        thread = threading.Thread(target=_pump, args=(proc, handle, tail, sink), daemon=True)
        thread.start()
    else:
        proc = subprocess.Popen(
            [resolve(args[0])] + args[1:],
            cwd=str(HERE),
            stdout=handle,
            stderr=subprocess.STDOUT,
            creationflags=NO_WINDOW
        )
        tail, thread = None, None

    RUNNING[name] = Child(proc, handle, thread, tail)
    return log_path, tail


def launch_window(name, ps_command):
    """Start a command inside its own visible PowerShell window.

    Python keeps the pwsh handle, so this stays killable - unlike the .bat,
    where 'start pwsh' threw the PID away and a PID file had to fake it.
    taskkill /T later kills pwsh AND the appium process underneath it.
    """
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        sys.exit("Neither pwsh nor powershell is on PATH.")

    # CREATE_NEW_CONSOLE is what gives it a separate window instead of
    # sharing this one.
    flags = subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0

    proc = subprocess.Popen(
        [shell, "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-Command", ps_command],
        cwd=str(HERE),
        creationflags=flags,
    )
    RUNNING[name] = Child(proc, None, None, None)


def read_log(log_path):
    """Return the log contents so far, or an empty string if it isn't there yet."""
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def stop(name):
    """Kill one child and its whole process tree."""
    child = RUNNING.pop(name, None)
    if child is None:
        return
    if child.tail is not None:
        child.tail.keep()               # stop the pump thread drawing to screen
    if child.proc.poll() is None:
        # /T also kills anything the child spawned, same as the .bat did.
        subprocess.run(
            ["taskkill", "/PID", str(child.proc.pid), "/F", "/T"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW
        )
    if child.thread is not None:
        child.thread.join(timeout=3)    # let the pump finish before the file closes
    if child.handle is not None:        # window-launched children have no handle
        child.handle.close()


def stop_all():
    for name in list(RUNNING):
        print(f"Stopping {name}")
        stop(name)

def stop_agent():
    """Shut down go-ios's tunnel agent.

    The agent is its own process, not a child of 'ios tunnel start', so
    taskkill /T misses it. Left running it keeps advertising the previous
    tunnel's RSD address and runwda dials a dead port.
    """
    subprocess.run(
        [resolve("ios"), "tunnel", "stopagent"],
        cwd=str(HERE),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

# ------------------------------------------------------------------- steps

def find_udid():
    """Ask go-ios which devices are attached and return one UDID.

    This replaces the hardcoded ID. The commented-out block in startup.bat
    was trying to do exactly this via 'ios list'.
    """
    result = subprocess.run(
        [resolve("ios"), "list"],
        cwd=str(HERE), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        creationflags=NO_WINDOW
    )
    found = list(dict.fromkeys(UDID_RE.findall(result.stdout + result.stderr)))

    if not found:
        print("No device found by 'ios list'. Check the cable, unlock the phone,")
        print("and make sure you have tapped Trust. Raw output:")
        print((result.stdout + result.stderr).strip() or "(nothing)")
        return None

    if UDID and UDID not in found:
        print(f"Configured UDID {UDID} is not attached. Attached: {', '.join(found)}")
        return None
    if UDID:
        return UDID

    if len(found) > 1:
        print(f"More than one device attached: {', '.join(found)}")
        print("Using the first one. Set UDID at the top of this file to pick.")
    return found[0]


def start_tunnel():
    stop_agent()
    wait(2)
    for attempt in range(1, TUNNEL_ATTEMPTS + 1):
        print(f"STARTING TUNNEL (attempt {attempt} of {TUNNEL_ATTEMPTS})")
        log_path, tail = launch("tunnel", ["ios", "tunnel", "start"], live=True)

        for _ in range(TUNNEL_POLLS):
            wait(TUNNEL_POLL_SECONDS)
            if TUNNEL_READY_MARKER in read_log(log_path):
                tail.wipe()
                print("TUNNEL STARTED")
                return True

        tail.keep()
        print("Tunnel timed out")
        stop("tunnel")
        wait(2)

    return False


def start_wda(udid):
    for attempt in range(1, WDA_ATTEMPTS + 1):
        print(f"STARTING WDA (attempt {attempt} of {WDA_ATTEMPTS})")
        log_path, tail = launch("runwda", [
            "ios", "runwda",
            f"--bundleid={WDA_BUNDLE}",
            f"--testrunnerbundleid={WDA_BUNDLE}",
            f"--xctestconfig={WDA_XCTEST}",
            f"--udid={udid}",
        ], live=True)

        wait(WDA_SETTLE_SECONDS)

        match = AUTHORIZED_RE.search(read_log(log_path))
        authorized = match.group(1).lower() if match else "not reported"

        if authorized == "true":
            tail.wipe()
            print("WDA IS RUNNING")
            return True

        tail.keep()
        print(f"WDA authorized? {authorized} - trying again")
        stop("runwda")
        wait(5)

    return False


def start_forward(udid):
    print("PORT FORWARDING WDA")
    launch("forward", ["ios", "forward", "8100", "8100", f"--udid={udid}"])
    launch("forward9100", ["ios", "forward", "9100", "9100", f"--udid={udid}"])
    wait(5)
    print("FORWARDED WDA @ http://localhost:8100/status")


def start_appium():
    print("STARTING APPIUM")
    launch("appium", ["appium", "--use-plugins=inspector"], live=True, sink=state.log_appium)
    wait(5)
    print("APPIUM STARTED @ http://localhost:4723")


# -------------------------------------------------------------------- main


def main():
    TEMP.mkdir(exist_ok=True)
    enable_ansi()
    threading.Thread(target=watch_for_enter, daemon=True).start()

    print("STARTUP  (press Enter or Ctrl+C at any time to terminate)\n")

    try:
        udid = find_udid()
        if udid is None:
            return
        print(f"This is your Device ID: {udid}\n")

        if not start_tunnel():
            print("Something has gone terribly wrong: tunnel never came up.")
            return
        print()

        if not start_wda(udid):
            print("Something has gone terribly wrong: WDA never authorized.")
            return
        print()

        start_forward(udid)
        start_appium()

        print("\nEverything is up. Press Enter to terminate.")
        state.publish(tunnel_state="Tunnel Open")
        while not STOP.wait(0.5):
            pass
    except Aborted:
        print("\nAborting.")
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        STOP.set()
        print("Terminating.")
        stop_all()
        stop_agent()


if __name__ == "__main__":
    main()
