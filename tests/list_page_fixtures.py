"""Shared helpers of the Test List page tests (``test_test_list_page.py``,
``test_test_list_actions.py``): tests in every state written through the store, a page
bound to a subject, and a signal recorder."""

from __future__ import annotations

from pathlib import Path

from src.engine.subject_tests import create_test, record_result
from src.ui.test_list_page import SubjectTestListPage
from src.ui.test_list_table import COL_NAME

SUBJECT = "TESTING"


def make_run_folder(root: Path, name: str = "2026-10-06_TESTING_click_grid_run1") -> Path:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def done_test(root, task="click_grid", name=None, *, planned=18, completed=18, folder=None, when=None):
    test = create_test(root, SUBJECT, task, name=name)
    folder = folder or make_run_folder(root, f"2026-10-06_TESTING_{task}_{test.test_id}")
    return record_result(
        root,
        SUBJECT,
        test.test_id,
        session_dir=folder,
        planned_trials=planned,
        completed_trials=completed,
        completed_at=when or "2026-10-06T12:00:00+00:00",
    )


def page_for(root, subject=SUBJECT) -> SubjectTestListPage:
    page = SubjectTestListPage()
    page.set_subject(subject, root)
    return page


def names(page) -> list[str]:
    return [row[COL_NAME] for row in page.row_texts()]


def select(page, test_id):
    assert page.select_test(test_id)


def enabled(page) -> dict[str, bool]:
    return {
        "add": page.add_button.isEnabled(),
        "configure": page.configure_button.isEnabled(),
        "run": page.run_button.isEnabled(),
        "report": page.report_button.isEnabled(),
        "copy": page.copy_button.isEnabled(),
        "delete": page.delete_button.isEnabled(),
    }


class Recorder:
    """Collects what a signal emits."""

    def __init__(self, signal):
        self.items = []
        signal.connect(lambda *args: self.items.append(args[0] if len(args) == 1 else args))
