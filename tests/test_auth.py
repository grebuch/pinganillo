import pytest

from escuchator.auth.chatgpt import ChatGPTAuth, validate_callback


def test_callback_accepts_matching_state_and_issued_client():
    params = {"state": ["ok"], "code": ["code"], "client_id": ["oaiapp_1"]}
    assert validate_callback(params, "ok") == ("oaiapp_1", "code")


@pytest.mark.parametrize(
    ("params", "client"),
    [
        ({"state": ["bad"]}, None),
        ({"state": ["ok"], "code": ["code"]}, None),  # new registration must return a client id
        ({"state": ["ok"], "code": ["c"], "client_id": ["dynamic_agent_client"]}, None),
        ({"state": ["ok"], "code": ["code"], "client_id": ["other"]}, "issued"),
        ({"state": ["ok"], "error": ["access_denied"]}, None),
    ],
)
def test_callback_rejects_invalid_redirects(params, client):
    with pytest.raises(ValueError):
        validate_callback(params, "ok", client)


def test_reauthorisation_may_omit_client_id():
    assert validate_callback({"state": ["s"], "code": ["c"]}, "s", "oaiapp_1") == ("oaiapp_1", "c")


def test_corrupt_registration_file_is_replaced(tmp_path):
    (tmp_path / "chatgpt_registrations.json").write_text("{not json", encoding="utf-8")
    auth = ChatGPTAuth(tmp_path)
    assert auth.config["host_id"].startswith("urn:uuid:")
    assert auth.registrations == []
    assert not auth.connected


def test_host_id_is_stable_between_runs(tmp_path):
    assert ChatGPTAuth(tmp_path).config["host_id"] == ChatGPTAuth(tmp_path).config["host_id"]
