import json
import os
import tempfile
import unittest
import requests
from pathlib import Path
from unittest.mock import patch

from workforce.openai_provider import ENDPOINT, OpenAIError, OpenAIProvider
from workforce.runtime import Workforce


SYSTEM = "Guardrails\nPERMISSIONS:\n" + json.dumps({
    "local_drafts": ["draft_note"], "approval_requests_only": ["send_message"],
})
DATA = {"brief": "Synthetic input only", "source_ids": ["fixture:1"], "country": "US"}


def completed():
    wire = {"summary": "Synthetic draft", "source_ids": ["fixture:1"],
            "actions": [{"kind": "draft_note", "payload_json": '{"test":true}'}],
            "escalations": []}
    return {"id": "resp_test", "model": "test-model", "status": "completed",
            "usage": {"input_tokens": 123, "output_tokens": 45},
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": json.dumps(wire)}]}]}


class OpenAITests(unittest.TestCase):
    def provider(self, **kwargs):
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://credential-proxy.invalid:8080"}):
            return OpenAIProvider(credential_proxy=True, **kwargs)

    def test_missing_explicit_proxy_mode_rejected(self):
        with self.assertRaises(ValueError):
            OpenAIProvider()

    def test_no_proxy_rejected(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIProvider(credential_proxy=True)

    def test_caps_validated(self):
        for kwargs in [{"max_calls": 0}, {"max_calls": 21},
                       {"max_output_tokens": 99999}, {"timeout": 1000}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.provider(**kwargs)

    def test_request_is_structured_no_tools_no_storage(self):
        provider = self.provider()
        with patch.object(provider, "_request", return_value=completed()) as request:
            output = provider.generate(system=SYSTEM, data=DATA)
        body = request.call_args.args[0]
        self.assertEqual(body["tools"], [])
        self.assertFalse(body["store"])
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertEqual(body["max_output_tokens"], 900)
        action = body["text"]["format"]["schema"]["properties"]["actions"]["items"]
        self.assertEqual(action["properties"]["kind"]["enum"], ["draft_note", "send_message"])
        self.assertEqual(output["actions"][0]["payload"], {"test": True})
        self.assertEqual(provider.last_usage["input_tokens"], 123)

    def test_no_redirect(self):
        provider = self.provider()
        with patch("requests.Session") as factory:
            session = factory.return_value.__enter__.return_value
            session.post.return_value.__enter__.return_value.status_code = 302
            with self.assertRaisesRegex(OpenAIError, "OpenAI_HTTP_302"):
                provider._request({})
            self.assertFalse(session.post.call_args.kwargs["allow_redirects"])
            self.assertEqual(session.post.call_count, 1)

    def test_http_body_redacted(self):
        provider = self.provider()
        with patch("requests.Session") as factory:
            response = factory.return_value.__enter__.return_value.post.return_value.__enter__.return_value
            response.status_code = 401
            with self.assertRaisesRegex(OpenAIError, "OpenAI_HTTP_401") as raised:
                provider._request({})
            response.iter_content.assert_not_called()
        self.assertNotIn("secret-test", str(raised.exception))

    def test_requests_transport_contract(self):
        provider = self.provider()
        with patch("requests.Session") as factory:
            session = factory.return_value.__enter__.return_value
            response = session.post.return_value.__enter__.return_value
            response.status_code = 200
            response.iter_content.return_value = [b'{"ok":', b'true}']
            self.assertEqual(provider._request({"fixture": True}), {"ok": True})
            args, kwargs = session.post.call_args
            self.assertEqual(args, (ENDPOINT,))
            self.assertEqual(json.loads(kwargs["data"]), {"fixture": True})
            self.assertEqual(kwargs["timeout"], (10, 45))
            self.assertTrue(kwargs["stream"])
            self.assertFalse(kwargs["allow_redirects"])
            self.assertNotIn("Authorization", kwargs["headers"])
            self.assertTrue(callable(session.auth))
            self.assertIs(session.auth(response), response)
        with requests.Session() as real_session:
            self.assertTrue(real_session.trust_env)
            self.assertTrue(real_session.verify)
            self.assertEqual(real_session.get_adapter(ENDPOINT).max_retries.total, 0)

    def test_requests_timeout_redacted_no_retry(self):
        with patch("requests.Session") as factory:
            post = factory.return_value.__enter__.return_value.post
            post.side_effect = requests.Timeout("secret-test-token")
            with self.assertRaisesRegex(OpenAIError, "^OpenAI_TransportFailure$"):
                self.provider()._request({})
            self.assertEqual(post.call_count, 1)

    def test_requests_response_size_limit(self):
        with patch("requests.Session") as factory:
            response = factory.return_value.__enter__.return_value.post.return_value.__enter__.return_value
            response.status_code = 200
            response.iter_content.return_value = [b"x" * 262144, b"x"]
            with self.assertRaisesRegex(OpenAIError, "ResponseSizeLimit"):
                self.provider()._request({})

    def test_requests_invalid_json(self):
        with patch("requests.Session") as factory:
            response = factory.return_value.__enter__.return_value.post.return_value.__enter__.return_value
            response.status_code = 200
            response.iter_content.return_value = [b"not json"]
            with self.assertRaisesRegex(OpenAIError, "OpenAI_InvalidResponse"):
                self.provider()._request({})

    def test_refusal_fails_closed(self):
        result = completed()
        result["output"][0]["content"] = [{"type": "refusal", "refusal": "No"}]
        provider = self.provider()
        with patch.object(provider, "_request", return_value=result):
            with self.assertRaisesRegex(OpenAIError, "Refusal"):
                provider.generate(system=SYSTEM, data=DATA)

    def test_error_code_rejects_arbitrary_text(self):
        self.assertEqual(OpenAIError("secret value").code, "OpenAI_InvalidResponse")
        self.assertNotIn("secret", str(OpenAIError("secret value")))

    def test_incomplete_not_accepted_and_usage_retained(self):
        result = completed()
        result["status"] = "incomplete"
        provider = self.provider()
        with patch.object(provider, "_request", return_value=result):
            with self.assertRaises(OpenAIError):
                provider.generate(system=SYSTEM, data=DATA)
        self.assertEqual(provider.last_usage["output_tokens"], 45)

    def test_non_object_payload_denied(self):
        result = completed()
        wire = json.loads(result["output"][0]["content"][0]["text"])
        wire["actions"][0]["payload_json"] = '["bad"]'
        result["output"][0]["content"][0]["text"] = json.dumps(wire)
        provider = self.provider()
        with patch.object(provider, "_request", return_value=result):
            with self.assertRaises(OpenAIError):
                provider.generate(system=SYSTEM, data=DATA)

    def test_live_call_cap_durable_across_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            provider = self.provider(max_calls=1)
            path = Path(temp) / "queue.sqlite"
            with patch.object(provider, "_request", return_value=completed()) as request:
                worker = Workforce(path, provider=provider)
                first = worker.submit("ai-customer-support", DATA, idempotency_key="one")
                self.assertEqual(worker.run(first)["status"], "completed")
                worker.close()
                worker = Workforce(path, provider=provider)
                second = worker.submit("ai-customer-support", DATA, idempotency_key="two")
                self.assertEqual(worker.run(second)["error_code"], "LiveCallCap")
                self.assertEqual(request.call_count, 1)
                self.assertEqual(worker.metrics()["live_call_reservations"], 1)
                worker.close()

    def test_failed_http_consumes_slot_no_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            provider = self.provider(max_calls=1)
            worker = Workforce(Path(temp) / "queue.sqlite", provider=provider)
            with patch.object(provider, "_request", side_effect=OpenAIError("OpenAI_HTTP_429")) as request:
                task = worker.submit("ai-customer-support", DATA, idempotency_key="one")
                self.assertEqual(worker.run(task)["status"], "failed")
                self.assertEqual(worker.task(task)["error_code"], "OpenAI_HTTP_429")
                worker.run(task)
                self.assertEqual(request.call_count, 1)
                self.assertEqual(worker.metrics()["live_call_reservations"], 1)
            worker.close()

    def test_usage_persists_when_business_rule_rejects_output(self):
        result = completed()
        wire = json.loads(result["output"][0]["content"][0]["text"])
        wire["actions"][0]["kind"] = "initiate_payment"
        result["output"][0]["content"][0]["text"] = json.dumps(wire)
        with tempfile.TemporaryDirectory() as temp:
            provider = self.provider()
            worker = Workforce(Path(temp) / "queue.sqlite", provider=provider)
            with patch.object(provider, "_request", return_value=result):
                task = worker.submit("ai-customer-support", DATA, idempotency_key="one")
                self.assertEqual(worker.run(task)["error_code"], "PermissionError")
                usage = json.loads(worker.metrics()["live_usage"][0]["usage_json"])
                self.assertEqual(usage["input_tokens"], 123)
            worker.close()


if __name__ == "__main__":
    unittest.main()
