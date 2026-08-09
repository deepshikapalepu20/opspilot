import json
import urllib.request
import urllib.error


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen2.5:3b-instruct"


def generate_response(prompt: str) -> str:
    """
    Send a prompt to the local Ollama LLM and return its response.
    """

    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))

        return result.get("response", "").strip()

    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Could not connect to Ollama at {OLLAMA_URL}. "
            f"Make sure Ollama is running. Error: {e}"
        )