"""What Save & Continue does with a configuration name (SPEC-compass-task-flow.md 4B.4, AB8,
AB9), as a pure decision.

The page hands over the name and the values it shows; this module says what has to happen
before they can be stored, without asking anyone or writing a file (the flow in
:mod:`src.ui.config_flow` does that):

* **Standard, values untouched** -- store the snapshot under "Standard"; no file.
* **Standard, values changed** -- "Standard cannot be changed": ask for a new name.
* **A name that is new** -- store the snapshot and write a profile file under it.
* **A name that exists, same values as its newest version** -- store the snapshot; no file.
* **A name that exists, different values** -- ask: Update it (a new version file under the
  same name), save under a new name, or cancel.

Values are compared after :func:`~src.ui.settings_snapshot.complete_settings`, so a saved
version that lacks a key (an older file) compares as the default for it. Names compare
case-insensitively, and an existing name keeps the spelling of its newest version.
Qt-free.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from ..engine.settings_profile import STANDARD_CONFIG_NAME, NamedConfig
from .settings_snapshot import complete_settings

STORE_STANDARD = "store_standard"
ASK_NEW_NAME = "ask_new_name"
NEW_CONFIGURATION = "new_configuration"
UNCHANGED = "unchanged"
ASK_UPDATE = "ask_update"

CUSTOM_PREFIX = "Custom"


@dataclass(frozen=True)
class SaveDecision:
    """``kind`` is one of the constants above. ``name`` is the configuration name to store
    (for ``ask_new_name`` it is "Standard", which cannot be stored). ``existing`` is the
    saved configuration the name matched, if any."""

    kind: str
    name: str
    existing: NamedConfig | None = None


def same_values(
    task_id: str,
    config: dict[str, Any],
    a: Mapping[str, Any],
    b: Mapping[str, Any],
) -> bool:
    """Do two ``{"live", "structural"}`` blocks mean the same settings for this task?"""
    first = complete_settings(task_id, config, a.get("live"), a.get("structural"))
    second = complete_settings(task_id, config, b.get("live"), b.get("structural"))
    return first == second


def decide_save(
    task_id: str,
    config: dict[str, Any],
    name: str,
    live: dict[str, Any],
    structural: dict[str, Any],
    standard: Mapping[str, Any],
    named: Mapping[str, NamedConfig],
) -> SaveDecision:
    """The 4B.4 rule for saving ``live`` / ``structural`` under ``name``.

    ``standard`` is the page's ``standard_values()``; ``named`` maps the case-folded name
    of each of this subject's saved configurations for the task to it.
    """
    entry = {"live": live, "structural": structural}
    name = name.strip()
    if name.casefold() == STANDARD_CONFIG_NAME.casefold():
        kind = STORE_STANDARD if same_values(task_id, config, entry, standard) else ASK_NEW_NAME
        return SaveDecision(kind, STANDARD_CONFIG_NAME)
    existing = named.get(name.casefold())
    if existing is None:
        return SaveDecision(NEW_CONFIGURATION, name)
    kind = UNCHANGED if same_values(task_id, config, entry, existing_values(existing)) else ASK_UPDATE
    return SaveDecision(kind, existing.name, existing)


def existing_values(config: NamedConfig) -> dict[str, Any]:
    return {"live": config.live, "structural": config.structural}


def next_custom_name(existing_names: Iterable[str]) -> str:
    """"Custom 1", or the next free number: the default of the new-name question."""
    taken = {n.strip().casefold() for n in existing_names}
    number = 1
    while f"{CUSTOM_PREFIX} {number}".casefold() in taken:
        number += 1
    return f"{CUSTOM_PREFIX} {number}"
