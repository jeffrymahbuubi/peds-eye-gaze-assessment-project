"""The recording client of a Mouse run that has no tracker
(SPEC-input-selection-and-follow.md H4, H5).

A Mouse test needs no tracker: the mouse is the pointer. When the Setup tab's tracker
is connected and calibrated it still records into the run; when it is not,
:class:`~src.app.AssessmentApp` is given this stand-in instead, so the code that asks
the client for device facts, raw records or a link state needs no ``None`` checks.
It has the surface of :class:`~src.inputs.gazepoint_client.GazepointClient` that the
app uses and reports "nothing": no sample, no raw record, not connected, not live.
"""

from __future__ import annotations

from ..data.schema import GazeSample


class NoTracker:
    device_info = None
    is_live = False

    def latest(self) -> GazeSample | None:
        return None

    def is_connected(self) -> bool:
        return False

    def connect(self, host: str = "127.0.0.1", port: int = 4242) -> None:
        return None

    def start_streaming(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def clear_raw(self) -> None:
        return None

    def drain_raw(self) -> list[tuple[int, dict[str, str]]]:
        return []
