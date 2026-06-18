import json

import requests


class OpenAICompatibleClient:
    def __init__(self, base_url, api_key=None, timeout=60, chat_options=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.chat_options = chat_options or {}
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def embed(self, model, text):
        try:
            response = self.session.post(
                f"{self.base_url}/embeddings",
                json={"model": model, "input": text},
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.ConnectionError as error:
            raise RuntimeError(f"Could not connect to embedding server at {self.base_url}") from error
        except Exception as error:
            raise RuntimeError(f"Embedding request failed: {error}") from error

        data = payload.get("data") or []
        if not data or "embedding" not in data[0]:
            raise RuntimeError(f"Embedding response missing vector: {payload}")
        return data[0]["embedding"]

    def chat(self, model, messages, temperature=0.1):
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        payload.update({key: value for key, value in self.chat_options.items() if value is not None})

        try:
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.exceptions.ConnectionError as error:
            raise RuntimeError(f"Could not connect to chat server at {self.base_url}") from error
        except Exception as error:
            raise RuntimeError(f"Chat request failed: {error}") from error

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError(f"Chat response missing choices: {payload}")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not content:
            raise RuntimeError(f"Chat response missing content: {payload}")
        return content.strip()


def parse_json_object(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found: {text}")
    return json.loads(cleaned[start : end + 1])
