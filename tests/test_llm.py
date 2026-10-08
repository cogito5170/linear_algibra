import json
import tempfile
import unittest
from types import SimpleNamespace

from math_study_agent.errors import LLMError
from math_study_agent.llm import AnthropicLLM, LLMRequest, ReplayLLM
from math_study_agent.schemas import wire_schema


class _Stream:
    def __init__(self, outcome):
        self.outcome = outcome

    def __enter__(self):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.outcome


class _Messages:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def stream(self, **kwargs):
        self.calls.append(kwargs)
        return _Stream(self.outcome)


def _client(outcome):
    return SimpleNamespace(messages=_Messages(outcome), beta=SimpleNamespace(messages=_Messages(outcome)))


def _message(text, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=10, output_tokens=20, cache_read_input_tokens=0),
    )


REQUEST = LLMRequest(agent="concept_mapper", system="sys", user="usr", output_schema_id="math_concept_map/1")


class AnthropicLLMTest(unittest.TestCase):
    def test_request_shape_with_fallbacks(self):
        client = _client(_message('{"ok": true}'))
        response = AnthropicLLM(client=client).generate_json(REQUEST)
        self.assertEqual(response.data, {"ok": True})
        self.assertEqual(response.usage["output_tokens"], 20)
        self.assertEqual(client.messages.calls, [])
        call = client.beta.messages.calls[0]
        self.assertEqual(call["model"], "claude-opus-5-5")
        self.assertEqual(call["thinking"], {"type": "adaptive"})
        self.assertEqual(call["output_config"]["effort"], "high")
        self.assertEqual(call["output_config"]["format"], {"type": "json_schema", "schema": wire_schema("math_concept_map/1")})
        self.assertEqual(call["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(call["fallbacks"], "default")
        self.assertEqual(call["system"], "sys")
        self.assertEqual(call["messages"], [{"role": "user", "content": "usr"}])

    def test_without_fallbacks_uses_plain_messages(self):
        client = _client(_message("{}"))
        AnthropicLLM(client=client, fallbacks=False, effort="medium").generate_json(REQUEST)
        self.assertEqual(client.beta.messages.calls, [])
        self.assertNotIn("betas", client.messages.calls[0])
        self.assertEqual(client.messages.calls[0]["output_config"]["effort"], "medium")

    def test_refusal_truncation_and_bad_json_raise(self):
        cases = [
            (_message("", "refusal"), "refusal"),
            (_message('{"a":', "max_tokens"), "truncated"),
            (_message("not json"), "invalid_json"),
            (RuntimeError("boom"), "api_error"),
        ]
        for outcome, kind in cases:
            with self.subTest(kind):
                with self.assertRaises(LLMError) as ctx:
                    AnthropicLLM(client=_client(outcome)).generate_json(REQUEST)
                self.assertEqual(ctx.exception.kind, kind)


class ReplayLLMTest(unittest.TestCase):
    def test_numbered_files_take_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path

            Path(tmp, "concept_mapper.json").write_text(json.dumps({"n": 0}))
            Path(tmp, "concept_mapper.2.json").write_text(json.dumps({"n": 2}))
            llm = ReplayLLM(tmp)
            self.assertEqual(llm.generate_json(REQUEST).data, {"n": 0})
            self.assertEqual(llm.generate_json(REQUEST).data, {"n": 2})
            with self.assertRaises(LLMError) as ctx:
                llm.generate_json(LLMRequest("note_editor", "", "", "math_study_note/1"))
            self.assertEqual(ctx.exception.kind, "replay_missing")


if __name__ == "__main__":
    unittest.main()
