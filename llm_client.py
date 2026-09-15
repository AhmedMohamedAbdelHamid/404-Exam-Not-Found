"""
llm_client.py — real LLM integration (replaces the call_llm stand-ins
in generate.py / generation_agent.py / validation_stage2.py).

Uses Gemini 2.5 Flash by default: cheapest current Gemini model with
reliable JSON-schema-constrained structured output, which is all this
task needs (grounded MCQ generation isn't a reasoning-heavy task that
benefits from a pricier model). Override with the GEMINI_MODEL env var
if the team wants a newer/stronger Flash variant later -- no code
change needed, just the env var.

--------------------------------------------------------------------
Setup (run these yourself -- this sandbox has no network access to
Google's API, so none of this has been tested against a live call):
--------------------------------------------------------------------
  pip install -r requirements.txt
  cp .env.example .env
  # edit .env and paste your key after GEMINI_API_KEY=
  # get a free key at https://aistudio.google.com/apikey -- Google AI
  # Studio's free tier is normally enough for hackathon-scale usage,
  # but check current limits yourself, they change.

.env is loaded automatically (via python-dotenv) the moment this
module is imported -- no need to `export` anything in your shell.
.env is gitignored; only .env.example (no real key) should ever be
committed.

Then generate.py / generation_agent.py's call_llm() functions
automatically use this module instead of their canned/stub responses
-- see USE_REAL_LLM below. Nothing else needs to change.

--------------------------------------------------------------------
Design: fails loudly, not silently.
--------------------------------------------------------------------
If GEMINI_API_KEY is set but the call fails (bad key, quota, network),
this raises LLMCallError with the real cause attached -- it does NOT
fall back to a stub. Silently returning fake data after a real call
was attempted would be far worse than crashing: a stub response
LOOKS valid (passes schema validation) but isn't grounded in anything
real, which is exactly the failure mode Stage 1/2 validation exists to
catch -- masking a real API failure behind fake-but-valid JSON would
defeat that.

The ONLY automatic fallback is when GEMINI_API_KEY isn't set at all
(local testing without a key) -- callers check USE_REAL_LLM themselves
and choose their own stub in that case; this module does not silently
substitute one.
"""

import os
import json
from pydantic import BaseModel

from schema import QuestionOut

# Load .env into os.environ if present. Safe to call even if no .env
# exists (e.g. CI, or a teammate using real shell exports instead) --
# load_dotenv() just no-ops. Must happen before GEMINI_MODEL/
# USE_REAL_LLM below read from os.environ.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv not installed -- .env won't be picked up
    # automatically, but real shell-exported env vars still work fine.
    pass

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
USE_REAL_LLM = bool(os.environ.get("GEMINI_API_KEY"))

_client = None


class LLMCallError(Exception):
    """Wraps any failure from a real Gemini call with the original
    exception attached as __cause__, plus enough context to debug
    without digging through the SDK's stack trace."""
    pass


class CritiqueResult(BaseModel):
    """Structured-output schema for Stage 2 self-critique (README 3.3's
    two yes/no questions). Kept local to this file, not schema.py --
    schema.py is the frozen Day-2 contract for QuestionOut/generation
    output; critique output is a different, internal shape that was
    never part of that freeze.
    """
    exactly_one_correct: bool
    supported_by_chunk: bool
    reasoning: str


def _get_client():
    global _client
    if _client is None:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise LLMCallError(
                "GEMINI_API_KEY is not set. Copy .env.example to .env "
                "and paste in a free key from "
                "https://aistudio.google.com/apikey"
            )
        _client = genai.Client(api_key=api_key)
    return _client


def _messages_to_gemini(messages: list[dict]) -> tuple[str | None, str]:
    """Our call sites use OpenAI-style messages: an optional
    {"role": "system", ...} plus one {"role": "user", ...}. Gemini
    takes the system prompt separately (system_instruction) and the
    rest as `contents`. If more than one non-system message is ever
    passed (e.g. future multi-turn retries), they're joined with role
    labels rather than dropped, so nothing is silently lost.
    """
    system_instruction = None
    other_parts = []
    for m in messages:
        if m["role"] == "system":
            system_instruction = m["content"]
        else:
            other_parts.append(m["content"])
    contents = "\n\n".join(other_parts)
    return system_instruction, contents


def _call_gemini(messages: list[dict], response_schema) -> str:
    if not USE_REAL_LLM:
        raise LLMCallError(
            "llm_client._call_gemini() was invoked but GEMINI_API_KEY "
            "is not set. Callers should check llm_client.USE_REAL_LLM "
            "before calling into this module, and use their own stub "
            "otherwise -- this module never silently substitutes fake "
            "data for a real call."
        )

    from google.genai import types

    client = _get_client()
    system_instruction, contents = _messages_to_gemini(messages)

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=response_schema,
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config,
        )
    except Exception as e:
        raise LLMCallError(
            f"Gemini API call failed (model={GEMINI_MODEL!r}). Check your "
            f"API key, quota, and network connection. Original error: {e}"
        ) from e

    if not response.text:
        raise LLMCallError(
            f"Gemini API returned an empty response (model={GEMINI_MODEL!r}). "
            f"This can happen if the safety filters blocked the output -- "
            f"check response.prompt_feedback if this recurs."
        )
    return response.text


def generate_question_json(messages: list[dict]) -> str:
    """Real signature: (messages) -> str, matching every call site's
    call_llm expectation exactly. Returns raw JSON text matching
    QuestionOut's shape (parse_and_validate() in prompt_template.py
    handles parsing/validation on the caller's side, same as it does
    for the stub responses today -- this function's only job is
    getting a real response, not validating it).
    """
    return _call_gemini(messages, response_schema=QuestionOut)


def critique_question_json(messages: list[dict]) -> str:
    """Real signature: (messages) -> str, matching
    validation_stage2.critique_question()'s call_llm_fn parameter
    exactly. Returns raw JSON text matching CritiqueResult's shape.
    """
    return _call_gemini(messages, response_schema=CritiqueResult)


if __name__ == "__main__":
    print("=" * 70)
    print("llm_client.py — configuration check (no live call possible")
    print("from this sandbox -- see module docstring)")
    print("=" * 70)
    print(f"GEMINI_MODEL: {GEMINI_MODEL}")
    print(f"USE_REAL_LLM (GEMINI_API_KEY set?): {USE_REAL_LLM}")

    if not USE_REAL_LLM:
        print(
            "\nNo GEMINI_API_KEY in this environment -- this is expected "
            "here. Run this file again on your own machine after "
            "`export GEMINI_API_KEY=...` to actually test a real call."
        )
    else:
        print("\nGEMINI_API_KEY is set -- attempting one real generation call...")
        test_messages = [
            {"role": "system", "content": "Respond with JSON: {\"ok\": true}"},
            {"role": "user", "content": "Confirm you're working."},
        ]
        try:
            from google.genai import types
            client = _get_client()
            resp = client.models.generate_content(
                model=GEMINI_MODEL, contents="Say hello in one word.",
            )
            print(f"✓ Real API call succeeded. Response: {resp.text!r}")
        except LLMCallError as e:
            print(f"✗ Real API call failed: {e}")
