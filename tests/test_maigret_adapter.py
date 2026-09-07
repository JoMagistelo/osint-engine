from threading import Event

from osint_engine.adapters.maigret_adapter import _ProgressNotifier


class _FoundStatus:
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
