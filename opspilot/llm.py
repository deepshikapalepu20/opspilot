import json
import os
import socket
import time
import urllib.request
import urllib.error
from typing import Any


# ============================================================
# OLLAMA CONFIGURATION
# ============================================================

OLLAMA_URL = os.environ.get(
    "OLLAMA_URL",
    "http://localhost:11434/api/chat",
)

MODEL_NAME = "qwen2.5:3b-instruct"

# Local models can take significant time to load and generate,
# especially on CPU.
OLLAMA_TIMEOUT = 300

# Number of times to retry a failed Ollama request.
OLLAMA_RETRIES = 2

# Keep the model loaded between requests.
# This avoids repeatedly loading the 3B model into memory.
OLLAMA_KEEP_ALIVE = "10m"


# ============================================================
# GROQ CONFIGURATION
# ============================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

GROQ_MODEL = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-20b",
)


class GroqError(Exception):
    """Raised when a Groq request fails."""
    pass


class GroqRateLimitError(GroqError):
    """Raised when Groq returns HTTP 429."""
    pass


# ============================================================
# OLLAMA CHAT
# ============================================================

def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Send a chat request to the local Ollama model.

    The model may either:

    1. Return a normal assistant response.
    2. Request one or more registered tools.

    This function is deliberately resilient because a local
    3B model can take a long time to load or generate output.
    """

    payload: dict[str, Any] = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,

        # Keep the model loaded between agent iterations.
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }

    if tools:
        payload["tools"] = tools

    data = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    last_error: Exception | None = None

    # ========================================================
    # RETRY LOOP
    # ========================================================

    for attempt in range(
        OLLAMA_RETRIES + 1
    ):

        request = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:

            print(
                f"\n[Ollama] Request "
                f"{attempt + 1}/{OLLAMA_RETRIES + 1} "
                f"using {MODEL_NAME}..."
            )

            start_time = time.time()

            with urllib.request.urlopen(
                request,
                timeout=OLLAMA_TIMEOUT,
            ) as response:

                raw_response = response.read()

            elapsed = time.time() - start_time

            print(
                f"[Ollama] Response received "
                f"in {elapsed:.1f}s"
            )

            # ------------------------------------------------
            # Decode JSON
            # ------------------------------------------------

            result = json.loads(
                raw_response.decode(
                    "utf-8"
                )
            )

            if not isinstance(
                result,
                dict,
            ):

                raise RuntimeError(
                    "Ollama returned a JSON response "
                    "that is not an object."
                )

            return result

        # ====================================================
        # TIMEOUT
        # ====================================================

        except (
            TimeoutError,
            socket.timeout,
        ) as e:

            last_error = e

            print(
                "\n[Ollama] Request timed out."
            )

            print(
                f"[Ollama] Timeout: "
                f"{OLLAMA_TIMEOUT}s"
            )

            if attempt < OLLAMA_RETRIES:

                print(
                    "[Ollama] Retrying..."
                )

                time.sleep(2)

                continue

            raise RuntimeError(
                f"Ollama request timed out after "
                f"{OLLAMA_TIMEOUT} seconds. "
                f"Model: {MODEL_NAME}. "
                "The local model may be taking too long "
                "to load or generate a response."
            ) from e

        # ====================================================
        # URL / CONNECTION ERROR
        # ====================================================

        except urllib.error.URLError as e:

            last_error = e

            # urllib can sometimes wrap a timeout inside
            # URLError rather than raising socket.timeout.
            reason = getattr(
                e,
                "reason",
                None,
            )

            if isinstance(
                reason,
                (
                    TimeoutError,
                    socket.timeout,
                ),
            ):

                print(
                    "\n[Ollama] Connection timed out."
                )

            else:

                print(
                    "\n[Ollama] Connection error:"
                )

                print(
                    str(e)
                )

            if attempt < OLLAMA_RETRIES:

                print(
                    "[Ollama] Retrying..."
                )

                time.sleep(2)

                continue

            raise RuntimeError(
                f"Could not connect to Ollama at "
                f"{OLLAMA_URL}. "
                "Make sure Ollama is running. "
                f"Model: {MODEL_NAME}. "
                f"Error: {e}"
            ) from e

        # ====================================================
        # INVALID JSON
        # ====================================================

        except json.JSONDecodeError as e:

            last_error = e

            print(
                "\n[Ollama] Invalid JSON response."
            )

            if attempt < OLLAMA_RETRIES:

                print(
                    "[Ollama] Retrying..."
                )

                time.sleep(1)

                continue

            raise RuntimeError(
                "Ollama returned an invalid JSON response."
            ) from e

        # ====================================================
        # OTHER ERRORS
        # ====================================================

        except Exception as e:

            last_error = e

            print(
                "\n[Ollama] Unexpected error:"
            )

            print(
                str(e)
            )

            if attempt < OLLAMA_RETRIES:

                print(
                    "[Ollama] Retrying..."
                )

                time.sleep(2)

                continue

            raise RuntimeError(
                f"Ollama request failed: {e}"
            ) from e

    # ========================================================
    # SHOULD NEVER BE REACHED
    # ========================================================

    raise RuntimeError(
        f"Ollama request failed after "
        f"{OLLAMA_RETRIES + 1} attempts."
    ) from last_error


# ============================================================
# GROQ CHAT
# ============================================================

def call_groq(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """
    Send a chat request to the Groq API.

    Groq uses an OpenAI-compatible chat completion endpoint.
    """

    if not GROQ_API_KEY:
        raise GroqError(
            "GROQ_API_KEY is not set."
        )

    payload: dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if tools:
        payload["tools"] = tools

    data = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        GROQ_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "User-Agent": "OpsPilot/1.0",
        },
        method="POST",
    )

    try:

        print(
            f"\n[Groq] Request using {GROQ_MODEL}..."
        )

        start_time = time.time()

        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:

            raw_response = response.read()

        elapsed = time.time() - start_time

        print(
            f"[Groq] Response received "
            f"in {elapsed:.1f}s"
        )

        result = json.loads(
            raw_response.decode("utf-8")
        )

        if not isinstance(
            result,
            dict,
        ):
            raise GroqError(
                "Groq returned a JSON response "
                "that is not an object."
            )

        return result

    except urllib.error.HTTPError as e:

        error_body = e.read().decode(
            "utf-8",
            errors="replace",
        )

        if e.code == 429:
            raise GroqRateLimitError(
                f"Groq rate limit hit: {error_body}"
            ) from e

        raise GroqError(
            f"Groq HTTP {e.code}: {error_body}"
        ) from e

    except urllib.error.URLError as e:

        raise GroqError(
            f"Groq network error: {e}"
        ) from e

    except json.JSONDecodeError as e:

        raise GroqError(
            "Groq returned invalid JSON."
        ) from e


# ============================================================
# RESPONSE NORMALIZATION
# ============================================================

def normalize_response(
    raw: dict[str, Any],
    provider: str,
) -> dict[str, Any]:
    """
    Convert Groq and Ollama responses into one
    consistent message format.
    """

    if provider == "groq":

        choices = raw.get(
            "choices",
            [],
        )

        if not choices:
            raise RuntimeError(
                "Groq returned no choices."
            )

        choice = choices[0].get(
            "message",
            {},
        )

        return {
            "role": choice.get(
                "role",
                "assistant",
            ),
            "content": choice.get(
                "content"
            ),
            "tool_calls": choice.get(
                "tool_calls"
            ),
        }

    # --------------------------------------------------------
    # OLLAMA
    # --------------------------------------------------------

    message = raw.get(
        "message",
        {},
    )

    return {
        "role": message.get(
            "role",
            "assistant",
        ),
        "content": message.get(
            "content"
        ),
        "tool_calls": message.get(
            "tool_calls"
        ),
    }


# ============================================================
# UNIFIED LLM CALL
# ============================================================

def call_llm(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Use Groq as the primary provider and Ollama
    as the automatic fallback.

    Both providers return the same normalized format.
    """

    try:

        raw = call_groq(
            messages,
            tools=tools,
            **kwargs,
        )

        print(
            "[llm] Using Groq."
        )

        return normalize_response(
            raw,
            "groq",
        )

    except GroqRateLimitError as e:

        print(
            f"[llm] Groq rate-limited: {e}"
        )

        print(
            "[llm] Falling back to Ollama."
        )

    except GroqError as e:

        print(
            f"[llm] Groq unavailable: {e}"
        )

        print(
            "[llm] Falling back to Ollama."
        )

    raw = chat(
        messages=messages,
        tools=tools,
    )

    return normalize_response(
        raw,
        "ollama",
    )


# ============================================================
# SIMPLE TEXT RESPONSE
# ============================================================

def generate_response(
    prompt: str,
) -> str:
    """
    Send a simple text prompt to Ollama and return
    the assistant's response.
    """

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    result = chat(
        messages=messages,
    )

    message = result.get(
        "message",
        {},
    )

    if not isinstance(
        message,
        dict,
    ):

        return ""

    return message.get(
        "content",
        "",
    ).strip()


# ============================================================
# LOCAL JSON RESPONSE
# ============================================================

def call_local_json(
    prompt: str,
) -> dict[str, Any]:
    """
    Send a prompt to the local Ollama model and parse
    the response as JSON.

    Used for:

    - RAG query reformulation
    - hypothesis generation
    - evidence verification
    - reflection
    - other structured reasoning
    """

    messages = [
        {
            "role": "user",
            "content": (
                prompt
                + "\n\n"
                + "Return ONLY valid JSON. "
                + "Do not include markdown fences "
                + "or explanatory text."
            ),
        }
    ]

    result = chat(
        messages=messages,
    )

    message = result.get(
        "message",
        {},
    )

    if not isinstance(
        message,
        dict,
    ):

        raise RuntimeError(
            "Ollama returned an invalid message object."
        )

    content = message.get(
        "content",
        "",
    ).strip()

    if not content:

        raise RuntimeError(
            "Ollama returned an empty response "
            "when JSON was expected."
        )

    # ========================================================
    # REMOVE MARKDOWN CODE FENCES
    # ========================================================

    if content.startswith(
        "```json"
    ):

        content = content[
            len("```json"):
        ]

    elif content.startswith(
        "```"
    ):

        content = content[
            len("```"):
        ]

    if content.endswith(
        "```"
    ):

        content = content[
            :-len("```")
        ]

    content = content.strip()

    # ========================================================
    # PARSE JSON
    # ========================================================

    try:

        parsed = json.loads(
            content
        )

    except json.JSONDecodeError as e:

        raise RuntimeError(
            "Ollama returned invalid JSON. "
            f"Response was: {content}"
        ) from e

    # ========================================================
    # ENSURE OBJECT
    # ========================================================

    if not isinstance(
        parsed,
        dict,
    ):

        raise RuntimeError(
            "Expected Ollama JSON response "
            "to be an object."
        )

    return parsed


# ============================================================
# AGENT DECISION
# ============================================================

def agent_decision(
    messages: list[dict[str, Any]],
    tool_definitions: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Ask the local Ollama model to decide what to do next.

    The model can:

    - request a tool call
    - return a normal response

    The programmatic agent_loop.py remains responsible for
    deciding whether the investigation is actually allowed
    to terminate.
    """

    message = call_llm(
        messages=messages,
        tools=tool_definitions,
    )

    if not isinstance(
        message,
        dict,
    ):

        return {
            "role": "assistant",
            "content": "",
        }

    return message