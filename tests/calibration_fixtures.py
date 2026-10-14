"""Shared stand-ins of the app-drawn calibration tests (SPEC-app-drawn-calibration.md section 6):
an in-process fake Gazepoint Control (``tools/fake_gazepoint_server.py``, which answers a
calibration with ``CAL`` records) and a client around a socket connected to it. No device, no
configured port: the listener binds an ephemeral one on 127.0.0.1."""

from __future__ import annotations

import importlib.util
import socket
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from src.data.schema import GazeSample
from src.engine.calibration import Calibration

FAKE_PATH = Path(__file__).resolve().parents[1] / "tools" / "fake_gazepoint_server.py"
_module = None


def fake_module():
    """``tools/fake_gazepoint_server.py`` loaded once (the module reads its port from argv)."""
    global _module
    if _module is None:
        spec = importlib.util.spec_from_file_location("_fake_gp_server_calibration", FAKE_PATH)
        module = importlib.util.module_from_spec(spec)
        old_argv = sys.argv
        sys.argv = ["fake_gazepoint_server.py"]
        try:
            spec.loader.exec_module(module)
        finally:
            sys.argv = old_argv
        _module = module
    return _module


class FakeControl:
    """A fake Gazepoint Control serving one connection; ``state`` is its calibration side."""

    def __init__(self) -> None:
        self.module = fake_module()
        self.state = self.module.CalibrationState()
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen(1)
        self.port = self._listener.getsockname()[1]
        self._socks: list[socket.socket] = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            conn, _addr = self._listener.accept()
        except OSError:
            return
        self.module.handle_client(conn, self.state)

    def client(self) -> SimpleNamespace:
        """A stand-in tracker client: what ``run_calibration`` needs is its socket."""
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=2)
        self._socks.append(sock)
        return SimpleNamespace(_sock=sock)

    def sync(self, client) -> None:
        """Return once the fake has handled everything sent so far (it reads in order): ask it
        something and wait for the answer."""
        client._sock.settimeout(2)
        client._sock.sendall(b'<GET ID="API_ID" />\r\n')
        seen = ""
        while 'ID="API_ID"' not in seen:
            seen += client._sock.recv(4096).decode("ascii", errors="ignore")

    def commands(self, command_id: str) -> list[str]:
        """The lines the fake received for ``command_id``, in order."""
        return [line for line in self.state.commands if f'ID="{command_id}"' in line]

    def close(self) -> None:
        for sock in self._socks:
            try:
                sock.close()
            except OSError:
                pass
        self._listener.close()
        self._thread.join(timeout=2)


def control_factory(client, log_path=None, n_points: int = 5):
    """The ``make_control`` the Setup page passes: today's ``Calibration`` with a Control window."""

    def make(**kwargs):
        return Calibration(client, n_points=n_points, enabled=True, show=True, timing_log_path=log_path, **kwargs)

    return make


class CapturingControl:
    """A ``make_control`` whose ``run()`` returns at once and remembers how it was asked."""

    def __init__(self, result) -> None:
        self.result = result
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(run=lambda: self.result)


def wait_until(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.005)


class FakeGaze:
    """What the tracker client's ``latest()`` is (the Check accuracy view's gaze source): the
    newest sample, replaced by ``look`` (a new ``t_ns`` each time, as a new REC would) or ``lose``
    (the link is gone)."""

    def __init__(self) -> None:
        self.sample: GazeSample | None = None
        self._n = 0

    def __call__(self) -> GazeSample | None:
        return self.sample

    def look(self, x: float, y: float, valid: bool = True) -> None:
        self._n += 1
        self.sample = GazeSample(t_ns=self._n, x=x, y=y, valid=valid)

    def lose(self) -> None:
        self.sample = None


def has_green(image, x: float, y: float, reach: int = 6) -> bool:
    """Whether a green-ish pixel of the ``QImage`` is within ``reach`` px of (x, y): the gaze
    trail's colour, which neither the background nor the (dark or light) ink of the rings is."""
    for px in range(int(x) - reach, int(x) + reach + 1):
        for py in range(int(y) - reach, int(y) + reach + 1):
            if 0 <= px < image.width() and 0 <= py < image.height():
                colour = image.pixelColor(px, py)
                if colour.green() - colour.red() >= 25 and colour.green() - colour.blue() >= 15:
                    return True
    return False
