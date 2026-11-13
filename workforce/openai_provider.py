"""OpenAI Responses adapter, authenticated only through a host-scoped proxy.

Run via the secure `pplx credentials run <returned-handle> -- ...` wrapper.
This module never loads a raw API key, accepts a custom endpoint, or enables tools.
"""
import json
import os
import re

ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.4-mini-2026-03-17"


class OpenAIError(RuntimeError):
    """Sanitized HTTP/provider failure without response body or credentials."""

    def __init__(self, code):
        allowed = {
            "ResponseSizeLimit", "OpenAI_TransportFailure", "OpenAI_InvalidResponse",
            "OpenAI_ResponseNotCompleted", "OpenAI_Refusal",
            "OpenAI_MissingStructuredOutput", "OpenAI_MalformedStructuredOutput",
        }
        self.code = code if isinstance(code, str) and (
            code in allowed or re.fullmatch(r"OpenAI_HTTP_[1-5][0-9]{2}", code)
        ) else "OpenAI_InvalidResponse"
        super().__init__(self.code)


class OpenAIProvider:
    name = "openai_responses"
    live = True

    def __init__(self, *, credential_proxy=False, model=DEFAULT_MODEL,
                 max_output_tokens=900, max_calls=3, timeout=45):
        if not credential_proxy or not (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")):
            raise ValueError("Run through the approved host-scoped credential proxy")
        if not isinstance(model, str) or not model or len(model) > 100:
            raise ValueError("Invalid model ID")
        if type(max_output_tokens) is not int or not 128 <= max_output_tokens <= 2000:
            raise ValueError("Output-token cap must be 128..2000")
        if type(max_calls) is not int or not 1 <= max_calls <= 20:
            raise ValueError("Live call cap must be 1..20")
        if not 1 <= timeout <= 60:
            raise ValueError("Timeout must be 1..60 seconds")
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.max_calls = max_calls
        self.timeout = timeout
        self.last_usage = None

    def _request(self, body):
        # Optional live dependency: offline operation does not import Requests.
        import requests

        encoded = json.dumps(body, allow_nan=False).encode()
        try:
            # Preserve environment proxy/CA configuration and TLS verification.
            # A no-op auth handler prevents implicit ~/.netrc credentials.
            with requests.Session() as session:
                session.auth = lambda request: request
                with session.post(
                    ENDPOINT, data=encoded, headers={"Content-Type": "application/json"},
                    timeout=(min(10, self.timeout), self.timeout),
                    allow_redirects=False, stream=True,
                ) as response:
                    if response.status_code != 200:
                        raise OpenAIError(f"OpenAI_HTTP_{response.status_code}")
                    raw = bytearray()
                    for chunk in response.iter_content(chunk_size=8192):
                        raw.extend(chunk)
                        if len(raw) > 262144:
                            raise OpenAIError("ResponseSizeLimit")
                return json.loads(raw)
        except (requests.RequestException, TimeoutError, OSError):
            raise OpenAIError("OpenAI_TransportFailure") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise OpenAIError("OpenAI_InvalidResponse") from None

    def generate(self, *, system, data):
        self.last_usage = None
        permissions = json.loads(system.rsplit("\nPERMISSIONS:\n", 1)[1])
        allowed = sorted(set(permissions["local_drafts"]) |
                         set(permissions["approval_requests_only"]))
        wire_schema = {
            "type": "object", "additionalProperties": False,
            "required": ["summary", "source_ids", "actions", "escalations"],
            "properties": {
                "summary": {"type": "string"},
                "source_ids": {"type": "array", "items": {"type": "string"}},
                "escalations": {"type": "array", "items": {"type": "string"}},
                "actions": {
                    "type": "array", "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["kind", "payload_json"],
                        "properties": {
                            "kind": {"type": "string", "enum": allowed},
                            "payload_json": {"type": "string"},
                        },
                    },
                },
            },
        }
        body = {
            "model": self.model,
            "instructions": system + (
                "\nTRANSPORT FORMAT: the JSON schema uses payload_json instead of payload. "
                "Encode each action payload as a JSON object serialized into that string. "
                "Use only supplied facts and source IDs. No tools or external actions exist."
            ),
            "input": [{"role": "user", "content": json.dumps(data, allow_nan=False)}],
            "store": False, "tools": [],
            "reasoning": {"effort": "none"},
            "max_output_tokens": self.max_output_tokens,
            "text": {"format": {
                "type": "json_schema", "name": "jci_workforce_result",
                "strict": True, "schema": wire_schema,
            }},
        }
        response = self._request(body)
        if not isinstance(response, dict):
            raise OpenAIError("OpenAI_InvalidResponse")
        usage = response.get("usage")
        if isinstance(usage, dict):
            self.last_usage = {
                "model": response.get("model", self.model),
                "response_id": response.get("id"),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            }
        if response.get("status") != "completed":
            raise OpenAIError("OpenAI_ResponseNotCompleted")
        parts = []
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "refusal":
                    raise OpenAIError("OpenAI_Refusal")
                if content.get("type") == "output_text":
                    parts.append(content["text"])
        if len(parts) != 1:
            raise OpenAIError("OpenAI_MissingStructuredOutput")
        try:
            wire = json.loads(parts[0])
            if set(wire) != {"summary", "source_ids", "actions", "escalations"}:
                raise ValueError("Unexpected fields")
            actions = []
            for action in wire["actions"]:
                if set(action) != {"kind", "payload_json"}:
                    raise ValueError("Unexpected action fields")
                payload = json.loads(action["payload_json"])
                if not isinstance(payload, dict):
                    raise ValueError("Payload is not an object")
                actions.append({"kind": action["kind"], "payload": payload})
            return {**wire, "actions": actions}
        except (ValueError, TypeError, KeyError):
            raise OpenAIError("OpenAI_MalformedStructuredOutput") from None
