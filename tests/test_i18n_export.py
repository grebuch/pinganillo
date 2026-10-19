import json
import queue

from pinganillo import i18n
from pinganillo.config import Settings
from pinganillo.export import diagnostics_report, session_to_json, session_to_markdown
from pinganillo.llm.analyzers import NoAnalyzer
from pinganillo.pipeline import Session, msg


def test_both_languages_define_the_same_keys():
    assert set(i18n.EN) == set(i18n.ES)


def test_messages_translate_with_parameters():
    i18n.set_language("es")
    try:
        assert (
            i18n.tr_message(msg("ai.waiting", seconds=3, limit=45)) == "Esperando a la IA · 3 s (límite 45 s)"
        )
        assert i18n.tr_message("plain text") == "plain text"
        assert i18n.tr("unknown.key") == "unknown.key"
    finally:
        i18n.set_language("en")


def _session():
    session = Session(None, NoAnalyzer(), None, events=queue.Queue())
    session.transcript = [{"hora": "10:00:01", "texto": "We need an RTO of four hours."}]
    session.summary = "Backup review."
    session.concepts = {"rto": {"termino": "RTO", "explicacion": "Recovery time objective."}}
    session.questions = {"q": {"pregunta": "Can we?", "breve": "Yes.", "faltan": "Budget"}}
    return session


def test_markdown_export_contains_every_section():
    text = session_to_markdown(_session())
    for fragment in (
        "Backup review.",
        "**RTO**",
        "**Can we?**",
        "Say: Yes.",
        "To confirm: Budget",
        "10:00:01",
    ):
        assert fragment in text


def test_json_export_round_trips():
    data = json.loads(session_to_json(_session()))
    assert data["concepts"][0]["termino"] == "RTO"
    assert data["transcript"][0]["texto"].startswith("We need")


def test_diagnostics_never_contain_meeting_content():
    session = _session()
    session.errors.append("error.analysis: HTTP 429 for user@example.com")
    report = diagnostics_report(Settings(), session)
    assert "RTO" not in report and "four hours" not in report and "example.com" not in report
    assert json.loads(report)["session"]["error_kinds"] == ["error.analysis"]
