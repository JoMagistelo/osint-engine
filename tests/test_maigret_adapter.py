import asyncio
import logging
from threading import Event

from osint_engine.adapters.maigret_adapter import MaigretAdapter, _ProgressNotifier
from osint_engine.normalization import UsernameCandidate


class _FoundStatus:
    def __init__(self, ids_data=None):
        self.ids_data = ids_data or {}
        self.query_time = 0.25
        self.tags = ["social"]

    def is_found(self):
        return True


class _MissingStatus:
    def is_found(self):
        return False


def test_progress_notifier_implements_current_maigret_contract():
    events = []

    def callback(engine, checked, total, detail):
        events.append((engine, checked, total, detail))

    notifier = _ProgressNotifier(
        "maigret",
        2,
        callback,
        identifier="alias",
        grand_total=2,
        cancel_event=Event(),
    )

    notifier.start("alias", "username")
    notifier.update(_FoundStatus())
    notifier.warning("retry")
    notifier.enrich("profile")
    notifier.update(_MissingStatus())
    notifier.finish()

    assert events
    assert events[-1][0] == "maigret"
    assert events[-1][1:3] == (2, 2)
    assert "1 coincidencias" in events[-1][3]


def test_progress_notifier_does_not_mark_cancelled_run_complete():
    events = []
    cancel_event = Event()
    cancel_event.set()

    notifier = _ProgressNotifier(
        "maigret",
        10,
        lambda *args: events.append(args),
        identifier="alias",
        grand_total=10,
        cancel_event=cancel_event,
    )

    notifier.update(_FoundStatus())
    notifier.finish()

    assert events[-1][1] == 1


def test_to_findings_reads_profile_metadata_from_maigret_status():
    candidate = UsernameCandidate(
        value="jose.gomez",
        origin="provided_username",
        confidence=1.0,
        relation="provided_username",
        parent_value="jose.gomez",
    )
    status = _FoundStatus(
        {
            "image": "https://example.test/avatar.jpg",
            "fullname": "José Gómez",
            "location": "México",
        }
    )
    findings = MaigretAdapter._to_findings(
        candidate,
        {
            "GitHub": {
                "status": status,
                "url_user": "https://github.com/jose.gomez",
                "url_main": "https://github.com/",
                "http_status": 200,
                "rank": 1,
            }
        },
    )

    assert len(findings) == 1
    evidence = findings[0].evidence
    assert evidence["profile_image_url"] == "https://example.test/avatar.jpg"
    assert evidence["ids_data"]["fullname"] == "José Gómez"
    assert evidence["query_time"] == 0.25


def test_notifier_smoke_test_with_installed_maigret_api():
    from maigret import search as maigret_search

    events = []
    notifier = _ProgressNotifier(
        "maigret",
        1,
        lambda *args: events.append(args),
        identifier="alias",
        grand_total=1,
        cancel_event=Event(),
    )

    result = asyncio.run(
        maigret_search(
            username="alias",
            site_dict={},
            logger=logging.getLogger("test.maigret"),
            query_notify=notifier,
            timeout=1,
            max_connections=1,
            no_progressbar=True,
        )
    )

    assert result == {}
    assert events
