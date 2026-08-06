"""Vision-backend abstraction for UX Lens's two Gemini vision call sites
(engine.py's DGA visual scan and ux/ux_visual_checks.py's UX visual scan).

Both call sites used to talk to `google.genai` directly. This module is the
seam: every Gemini-specific request detail — `thinking_config`,
`response_schema`, the `box_2d` 0-1000 prompt convention, the google-genai
SDK itself — lives ONLY in GeminiVisionProvider below. Call sites talk to
`VisionProvider.analyze_tile()` and select a backend via `get_vision_provider()`
(env `VISION_PROVIDER=gemini|ministry`); they never import a provider SDK.

======================================================================
THE UNVERIFIED PART — read before trusting MinistryVisionProvider in prod
======================================================================
No request was sent to the ministry gateway to write this — that is a live
production service and this task was explicitly told not to probe it.
Everything below was read straight out of ../autoglean's code, the only real
client of that gateway in this codebase family
(../autoglean/autoglean/llm/client.py, config/llm.yaml,
public_api/llm_routes.py). Grepped autoglean's whole repo for
`response_format|json_schema|structured_output` and for
`box_2d|bounding|grounding|bbox`: zero hits on either. Autoglean only ever
asks this endpoint to transcribe a page to markdown text; it has never asked
it for coordinates of anything, structured or otherwise.

What IS established (fact, read off autoglean's code):
  - Transport: plain OpenAI-compatible `POST {VISION_API_BASE}/chat/completions`
    via httpx directly — no vendor SDK. Model id from `VISION_MODEL`
    (autoglean's corp/server envs: "qwen3-vl"; local LM Studio dev:
    "qwen/qwen3-vl-30b").
  - Auth: `Authorization: Bearer {VISION_API_KEY}`.
  - Image input: an OpenAI `image_url` content part on the user message,
    `{"type": "image_url", "image_url": {"url": "data:{mime};base64,..."}}}`
    — NOT a Gemini-style inline blob.
  - Output: `choices[0].message.content` — a plain STRING. No
    `response_format` / JSON-schema / guided-decoding parameter is ever sent.
  - Autoglean's own `/api/v1/llm` passthrough (public_api/llm_routes.py) is
    TEXT-ONLY (`LLMMessage.content: str`) and cannot carry an image at all —
    it is not usable for this product's vision calls. UX Lens must speak to
    VISION_API_BASE directly, the same way autoglean's own LLMClient does
    (same env vars: VISION_API_BASE / VISION_API_KEY / VISION_MODEL, plus
    VISION_VERIFY_SSL mirroring autoglean's ssl_verify knob for the corp
    gateway's self-signed cert).

What this does NOT establish, and could not without calling the live
endpoint:
  - Whether the deployed qwen3-vl serving stack honours a request for
    coordinates at all, in what convention (pixel vs 0-1000/0-1 normalised,
    corner-pair vs center+size, axis order), or with what accuracy. Qwen-VL
    checkpoints have historically supported *some* grounding convention, but
    that is model/fine-tune/serving-stack dependent and unverified here.
  - Whether the gateway supports any structured-output / guided-decoding mode.
    If it does, MinistryVisionProvider should be upgraded to use it instead
    of the best-effort text parsing it does below — strictly weaker than
    Gemini's `response_schema` guarantee.

Bottom line: MinistryVisionProvider asks the model, in the prompt text, for
the same JSON-array-with-box_2d shape Gemini is asked for (build_prompt() /
build_ux_visual_prompt() are unchanged), and parses whatever text comes back
as leniently as possible. A missing or malformed `box_2d` is treated as "no
location available" — never a crash, never a fabricated box (see
`to_box()`'s two-tuple return in engine.py / ux/ux_visual_checks.py, and
`_normalize_ministry_item` below). **This must be verified against the real
endpoint before the ministry backend is trusted in production** — send one
real tile through it, log the raw `content` string, and check by eye whether
usable box_2d values come back at all.

If boxes never come back: UX Lens keeps working — rule_id / severity /
confidence / evidence / recommendation still flow through, scoring is
unaffected (score_of() counts violated rule ids, not boxes), and the
frontend already renders a violation with no on-screen highlight whenever
`region` is absent (src/services/api.ts's `Rule.region` is optional; every
render site in src/routes/results.tsx null-checks it — this was already true
for the pre-existing `manual_review` status, so no frontend change was
needed). What is lost is the product's headline feature: pointing at *where*
on the screenshot a violation is. A text-only finding list is still a
materially useful DGA/UX audit; it is just a different, less visual product
than the one built for Gemini.
======================================================================
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from google import genai
from google.genai import errors, types
from PIL import Image
from pydantic import BaseModel

logger = logging.getLogger("uxlens.vision")

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"


def _coerce_ssl_verify(value: Any) -> bool | str:
    """Same convention as autoglean's LLMClient._coerce_ssl_verify: True/False,
    or a CA-bundle path string. Kept local (not imported from autoglean — the
    two repos deploy independently) but the semantics match on purpose."""
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    text = str(value).strip()
    if text.lower() in ("true", "1", "yes", ""):
        return True
    if text.lower() in ("false", "0", "no"):
        return False
    return text


class VisionProvider(ABC):
    """One image tile in, a list of parsed violation dicts out."""

    @abstractmethod
    def analyze_tile(
        self,
        image: Image.Image,
        prompt: str,
        *,
        system_instruction: str,
        response_model: type[BaseModel],
        max_output_tokens: int,
        timeout_s: float = 30.0,
    ) -> tuple[list[dict], bool]:
        """Returns (items, ok).

        ok=False means the call/parse failed outright (network error, gateway
        error, unparseable response) — callers treat this as "could not
        analyze this tile", not "zero violations found", and some of them
        (ux/ux_visual_checks.py) surface that distinction to the user as
        'undetermined' rather than silently reporting 'pass'.

        Each item in `items` is a plain dict. `rule_id`, `severity`,
        `confidence`, `evidence`, `recommendation` are always present
        (defaulted by the provider if the backend omitted them). `box_2d`
        (a `[ymin, xmin, ymax, xmax]` list, 0-1000 normalised) is present
        ONLY if the backend actually supplied one — callers must use
        `.get("box_2d")` and treat its absence as "no location available",
        never crash on it and never invent a box.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def cache_key_component(self) -> str:
        """A short string identifying (backend, model) for cache-key hashing —
        see engine.py / ux_visual_checks.py's RULES_SIG. Ensures switching
        VISION_PROVIDER busts the tile-analysis cache instead of silently
        mixing results from two different backends under one cache key."""
        raise NotImplementedError


class GeminiVisionProvider(VisionProvider):
    """The original behaviour, unchanged: google-genai, response_schema
    structured output, thinking disabled, box_2d 0-1000 convention."""

    def __init__(self, api_key: str, model: str = DEFAULT_GEMINI_MODEL):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def cache_key_component(self) -> str:
        return f"gemini:{self._model}"

    def _gen(self, **kw):
        for attempt in range(1, 5):
            try:
                return self._client.models.generate_content(**kw)
            except (errors.ServerError, errors.ClientError) as e:
                transient = isinstance(e, errors.ServerError) or getattr(e, "code", None) == 429
                if not transient or attempt == 4:
                    raise
                time.sleep(5 * attempt)

    def analyze_tile(self, image, prompt, *, system_instruction, response_model,
                      max_output_tokens, timeout_s=30.0):
        try:
            r = self._gen(
                model=self._model,
                contents=[image, prompt],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0,
                    max_output_tokens=max_output_tokens,
                    response_mime_type="application/json",
                    response_schema=list[response_model],
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
                ),
            )
            return json.loads(r.text), True
        except Exception:
            logger.warning("gemini vision call failed", exc_info=True)
            return [], False


# ---- Ministry gateway provider ---------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_REQUIRED_DEFAULTS = {
    "severity": "Warning",
    "confidence": "منخفضة",
    "evidence": "",
    "recommendation": "",
}


def _extract_json_array(content: str) -> list | None:
    """Best-effort JSON-array extraction from a chat-completion text reply.

    Tries, in order: the whole string as JSON; a ```json fenced block; the
    widest [...] span in the string. Returns None if nothing parses — the
    caller treats that as a failed call (ok=False), same as a transport
    error, since there is nothing usable to report either way.
    """
    content = (content or "").strip()
    if not content:
        return None
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else None
    except json.JSONDecodeError:
        pass
    m = _JSON_FENCE_RE.search(content)
    if m:
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    start, end = content.find("["), content.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(content[start:end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    return None


def _normalize_ministry_item(raw: Any) -> dict | None:
    """Shape one gateway-returned object into what engine.py / ux_visual_checks.py
    expect, without ever raising on a missing/wrong-typed field — this backend's
    output shape is unverified, so every field is optional except rule_id.

    box_2d is copied over ONLY if it is a 4-element list — anything else
    (absent, wrong length, non-numeric) is dropped silently so downstream
    `to_box()` sees a genuinely-missing key and reports 'no location', per
    this module's docstring, rather than choking on a malformed one.
    """
    if not isinstance(raw, dict):
        return None
    rule_id = raw.get("rule_id")
    if not rule_id or not isinstance(rule_id, str):
        return None
    item: dict = {"rule_id": rule_id}
    for key, default in _REQUIRED_DEFAULTS.items():
        val = raw.get(key)
        item[key] = val if isinstance(val, str) and val else default
    box = raw.get("box_2d")
    if (isinstance(box, list) and len(box) == 4
            and all(isinstance(v, (int, float)) for v in box)):
        item["box_2d"] = box
    return item


class MinistryVisionProvider(VisionProvider):
    """Ministry LLM gateway, OpenAI-compatible /chat/completions — see the
    module docstring for exactly what is and isn't verified about this."""

    def __init__(self, api_base: str, api_key: str, model: str,
                 verify_ssl: bool | str = True, max_retries: int = 3):
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._verify_ssl = verify_ssl
        self._max_retries = max_retries
        self._client: httpx.Client | None = None

    @property
    def cache_key_component(self) -> str:
        return f"ministry:{self._model}"

    def _http(self, timeout_s: float) -> httpx.Client:
        # Lazily built (and rebuilt if the timeout changes) so constructing a
        # provider instance for a health check never opens a connection.
        if self._client is None or self._client.timeout.read != timeout_s:
            if self._client is not None:
                self._client.close()
            self._client = httpx.Client(verify=self._verify_ssl, timeout=timeout_s)
        return self._client

    @staticmethod
    def _encode_tile(image: Image.Image) -> str:
        # JPEG, not PNG: screenshots tiled at 1600px tall re-encode to a
        # fraction of PNG's size, which matters on the corp gateway autoglean's
        # own client.py describes as flaky/slow — smaller payloads mean fewer
        # timeouts. Quality 92 keeps UI text legible for the model.
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=92)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def analyze_tile(self, image, prompt, *, system_instruction, response_model,
                      max_output_tokens, timeout_s=30.0):
        # response_model is intentionally unused here — no confirmed schema-
        # enforcement API on this gateway (see module docstring). Kept in the
        # signature for interface parity with GeminiVisionProvider.
        del response_model
        b64 = self._encode_tile(image)
        body = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": max_output_tokens,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]},
            ],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        url = f"{self._api_base}/chat/completions"
        client = self._http(timeout_s)

        content: str | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = client.post(url, headers=headers, json=body)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteError,
                    httpx.RemoteProtocolError) as e:
                if attempt == self._max_retries:
                    logger.warning("ministry vision call failed (transport): %s", e)
                    return [], False
                time.sleep(2 * attempt)
                continue

            if resp.status_code >= 500 and attempt < self._max_retries:
                time.sleep(2 * attempt)
                continue
            if resp.status_code >= 400:
                logger.warning("ministry vision call failed: HTTP %d: %.500s",
                                resp.status_code, resp.text)
                return [], False

            try:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
            except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
                logger.warning("ministry vision call returned unexpected shape: %s", e)
                return [], False
            break

        if content is None:
            return [], False

        parsed = _extract_json_array(content)
        if parsed is None:
            logger.warning("ministry vision response was not a parseable JSON array "
                            "(first 200 chars): %.200r", content)
            return [], False

        items = [it for it in (_normalize_ministry_item(p) for p in parsed) if it is not None]
        return items, True


# ---- Factory -----------------------------------------------------------

def cache_key_id() -> str:
    """The same (backend, model) identity get_vision_provider() would build a
    provider from, computed from env with no I/O — used for the tile-analysis
    cache signature (engine.py / ux/ux_visual_checks.py's RULES_SIG) so a
    cache populated under one backend is never silently reused for another.
    Safe to call at import time, unlike get_vision_provider() (which requires
    the chosen backend's credentials to actually be set)."""
    backend = os.environ.get("VISION_PROVIDER", "gemini").strip().lower()
    if backend == "ministry":
        return f"ministry:{os.environ.get('VISION_MODEL', '').strip()}"
    return f"gemini:{os.environ.get('GEMINI_MODEL', DEFAULT_GEMINI_MODEL).strip()}"


def get_vision_provider() -> VisionProvider:
    """Reads env fresh on every call (cheap: constructing a provider does no
    I/O) so callers — including tests — never see a stale backend choice."""
    backend = os.environ.get("VISION_PROVIDER", "gemini").strip().lower()

    if backend == "ministry":
        api_base = os.environ.get("VISION_API_BASE", "").strip()
        model = os.environ.get("VISION_MODEL", "").strip()
        if not api_base or not model:
            raise RuntimeError(
                "VISION_PROVIDER=ministry requires VISION_API_BASE and VISION_MODEL"
            )
        return MinistryVisionProvider(
            api_base=api_base,
            api_key=os.environ.get("VISION_API_KEY", ""),
            model=model,
            verify_ssl=_coerce_ssl_verify(os.environ.get("VISION_VERIFY_SSL", "true")),
        )

    if backend != "gemini":
        raise RuntimeError(f"unknown VISION_PROVIDER={backend!r} (expected 'gemini' or 'ministry')")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("VISION_PROVIDER=gemini requires GEMINI_API_KEY")
    return GeminiVisionProvider(api_key=api_key, model=os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL))
