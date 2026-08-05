from ai_client import DEFAULT_MODEL, complete


def test_default_model_is_legacy():
    # Intentionally asserts the legacy id so self-correct / patch can update it.
    assert DEFAULT_MODEL == "gpt-4-0613"


def test_complete_uses_model(monkeypatch):
    calls = {}

    class FakeMessage:
        content = "ok"

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            calls.update(kwargs)
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr("ai_client.build_client", lambda: FakeClient())
    assert complete("hi") == "ok"
    assert calls["model"] == "gpt-4-0613"
    assert "max_tokens" in calls
