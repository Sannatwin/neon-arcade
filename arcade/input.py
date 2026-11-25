from __future__ import annotations

from collections import deque
import os
import select
import sys
import time
from typing import Deque, List, Optional

if os.name != "nt":
    import termios
    import tty


KEY_UP = "UP"
KEY_DOWN = "DOWN"
KEY_LEFT = "LEFT"
KEY_RIGHT = "RIGHT"
KEY_SPACE = "SPACE"
KEY_ENTER = "ENTER"
KEY_ESC = "ESC"
KEY_BACKSPACE = "BACKSPACE"


class KeyboardReader:
    """Non-blocking terminal keyboard reader supporting arrow keys and WASD."""

    def __init__(self, stream=None) -> None:
        self._stream = stream or sys.stdin
        self._fd: Optional[int] = None
        self._old_settings = None
        self._active = False
        self._buffer: Deque[str] = deque()

    def __enter__(self) -> "KeyboardReader":
        if os.name == "nt":
            self._active = True
            return self

        if hasattr(self._stream, "isatty") and self._stream.isatty():
            self._fd = self._stream.fileno()
            self._old_settings = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)
            self._active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if os.name != "nt" and self._fd is not None and self._old_settings is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
        self._active = False

    def poll_keys(self, timeout: float = 0.0) -> List[str]:
        """Read all currently pending keypresses without blocking beyond timeout."""
        if not self._active:
            return []

        keys: List[str] = []
        while self._buffer:
            keys.append(self._buffer.popleft())

        if os.name == "nt":
            keys.extend(self._poll_windows())
            if not keys and timeout > 0:
                deadline = time.monotonic() + timeout
                while not keys and time.monotonic() < deadline:
                    time.sleep(min(0.01, max(0.0, deadline - time.monotonic())))
                    keys.extend(self._poll_windows())
            return keys

        if self._fd is None:
            return keys

        wait = 0.0 if keys else max(0.0, timeout)
        ready, _, _ = select.select([self._fd], [], [], wait)
        if not ready:
            return keys

        raw = os.read(self._fd, 64)
        # If an escape byte arrived alone, give a brief window for the rest of the sequence.
        if raw.endswith(b"\x1b"):
            more, _, _ = select.select([self._fd], [], [], 0.008)
            if more:
                raw += os.read(self._fd, 32)

        keys.extend(parse_escape_bytes(raw))
        return keys

    def wait_key(self, timeout: Optional[float] = None) -> Optional[str]:
        """Wait for at least one key and return the first parsed key."""
        if not self._active:
            return None
        if self._buffer:
            return self._buffer.popleft()
        if os.name == "nt":
            deadline = None if timeout is None else time.monotonic() + max(0.0, timeout)
            while True:
                keys = self._poll_windows()
                if keys:
                    self._buffer.extend(keys[1:])
                    return keys[0]
                if deadline is not None and time.monotonic() >= deadline:
                    return None
                time.sleep(0.01)
        if self._fd is None:
            return None

        ready, _, _ = select.select([self._fd], [], [], timeout)
        if not ready:
            return None
        keys = self.poll_keys(timeout=0.0)
        if not keys:
            return None
        self._buffer.extend(keys[1:])
        return keys[0]

    def _poll_windows(self) -> List[str]:
        import msvcrt

        keys: List[str] = []
        while msvcrt.kbhit():
            ch = msvcrt.getch()
            if ch == b"\x03":
                raise KeyboardInterrupt
            if ch in (b"\x00", b"\xe0") and msvcrt.kbhit():
                code = msvcrt.getch()
                mapping = {
                    b"H": KEY_UP,
                    b"P": KEY_DOWN,
                    b"K": KEY_LEFT,
                    b"M": KEY_RIGHT,
                }
                if code in mapping:
                    keys.append(mapping[code])
            else:
                keys.extend(parse_escape_bytes(ch))
        return keys


def parse_escape_bytes(data: bytes) -> List[str]:
    """Decode raw terminal input bytes into normalized key names."""
    keys: List[str] = []
    i = 0
    n = len(data)
    while i < n:
        byte = data[i : i + 1]
        if byte == b"\x1b":
            if i + 2 < n and data[i + 1 : i + 2] in (b"[", b"O"):
                code = data[i + 2 : i + 3]
                arrow_map = {
                    b"A": KEY_UP,
                    b"B": KEY_DOWN,
                    b"C": KEY_RIGHT,
                    b"D": KEY_LEFT,
                }
                if code in arrow_map:
                    keys.append(arrow_map[code])
                    i += 3
                    continue
                # Skip unknown CSI sequence up to final byte
                j = i + 2
                while j < n and not (0x40 <= data[j] <= 0x7E):
                    j += 1
                i = min(n, j + 1)
                continue
            keys.append(KEY_ESC)
            i += 1
            continue

        if byte in (b"\r", b"\n"):
            keys.append(KEY_ENTER)
        elif byte == b" ":
            keys.append(KEY_SPACE)
        elif byte in (b"\x7f", b"\x08"):
            keys.append(KEY_BACKSPACE)
        else:
            try:
                ch = byte.decode("utf-8").lower()
                if ch.isprintable():
                    keys.append(ch)
            except UnicodeDecodeError:
                pass
        i += 1
    return keys
