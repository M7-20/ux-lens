"""Tests for vision_provider.py — the vision-backend abstraction added to join
the waha platform (see vision_provider.py's module docstring for the full
context: what is/isn't verified about the ministry gateway backend).

No test here calls a real network endpoint. Gemini calls are exercised by
monkeypatching the wrapped google-genai client; ministry-gateway calls are
exercised by monkeypatching httpx.Client.post. This is the FIRST test suite
in this repo (audit-service/ had none before) — scoped to the new provider
abstraction and the box-degrade logic it required in engine.py /
ux/ux_visual_checks.py, not a retrofit of coverage for the rest of the app.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from pydantic import BaseModel

import vision_provider as vp


class DummyModel(BaseModel):
    box_2d: list[int]
    rule_id: str
    severity: str
    confidence: str
    evidence: str
    recommendation: str


def make_image() -> Image.Image:
    return Image.new("RGB", (10, 10))


def _mk_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = text
    return resp


# ---------------------------------------------------------------- _extract_json_array

def test_extract_json_array_plain():
    assert vp._extract_json_array('[{"a": 1}]') == [{"a": 1}]


def test_extract_json_array_fenced():
    text = 'here you go:\n```json\n[{"a": 1}]\n```\nthanks'
    assert vp._extract_json_array(text) == [{"a": 1}]


def test_extract_json_array_embedded_in_prose():
    text = 'Sure! [{"a": 1}, {"b": 2}] is the result.'
    assert vp._extract_json_array(text) == [{"a": 1}, {"b": 2}]


def test_extract_json_array_none_for_garbage():
    assert vp._extract_json_array("not json at all") is None


def test_extract_json_array_none_for_bare_object():
    # A JSON *object* (not array) is not a violations list — reject, don't
    # silently wrap it.
    assert vp._extract_json_array('{"a": 1}') is None


def test_extract_json_array_empty_string():
    assert vp._extract_json_array("") is None
    assert vp._extract_json_array(None) is None  # defensive: never crash on None


# ---------------------------------------------------------------- _normalize_ministry_item

def test_normalize_keeps_valid_box():
    item = vp._normalize_ministry_item({
        "rule_id": "DGA-X", "severity": "Error", "confidence": "عالية",
        "evidence": "ev", "recommendation": "rec", "box_2d": [1, 2, 3, 4],
    })
    assert item["box_2d"] == [1, 2, 3, 4]
    assert item["rule_id"] == "DGA-X"


def test_normalize_drops_missing_box_but_keeps_finding():
    """The central degrade case this whole module exists for: no box_2d at
    all from the gateway must not lose the finding."""
    item = vp._normalize_ministry_item({"rule_id": "DGA-X"})
    assert item is not None
    assert "box_2d" not in item
    assert item["severity"] == "Warning"       # defaulted
    assert item["confidence"] == "منخفضة"       # defaulted
    assert item["evidence"] == ""
    assert item["recommendation"] == ""


@pytest.mark.parametrize("bad_box", [
    [1, 2, 3],            # wrong length
    "not-a-list",         # wrong type
    [1, 2, 3, "x"],       # non-numeric element
    None,
    123,
])
def test_normalize_drops_malformed_box(bad_box):
    item = vp._normalize_ministry_item({"rule_id": "DGA-X", "box_2d": bad_box})
    assert item is not None
    assert "box_2d" not in item


def test_normalize_rejects_missing_rule_id():
    assert vp._normalize_ministry_item({"severity": "Error"}) is None
    assert vp._normalize_ministry_item({"rule_id": ""}) is None


def test_normalize_rejects_non_dict():
    assert vp._normalize_ministry_item("not a dict") is None
    assert vp._normalize_ministry_item([1, 2]) is None
    assert vp._normalize_ministry_item(None) is None


# ---------------------------------------------------------------- MinistryVisionProvider

def test_ministry_analyze_tile_happy_path():
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k", model="qwen3-vl")
    content = json.dumps([{"rule_id": "DGA-X", "severity": "Error", "confidence": "عالية",
                            "evidence": "ev", "recommendation": "rec", "box_2d": [1, 2, 3, 4]}])
    resp = _mk_response(json_data={"choices": [{"message": {"content": content}}]})
    with patch.object(vp.httpx.Client, "post", return_value=resp):
        items, ok = provider.analyze_tile(
            make_image(), "prompt", system_instruction="sys",
            response_model=DummyModel, max_output_tokens=100,
        )
    assert ok is True
    assert len(items) == 1
    assert items[0]["rule_id"] == "DGA-X"
    assert items[0]["box_2d"] == [1, 2, 3, 4]


def test_ministry_analyze_tile_no_box_in_response():
    """THE unverified case this task is centrally about: the model returns a
    real finding with no box_2d at all. The provider must still surface it,
    not drop it and not crash."""
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k", model="qwen3-vl")
    content = json.dumps([{"rule_id": "DGA-X", "severity": "Warning", "evidence": "ev"}])
    resp = _mk_response(json_data={"choices": [{"message": {"content": content}}]})
    with patch.object(vp.httpx.Client, "post", return_value=resp):
        items, ok = provider.analyze_tile(
            make_image(), "prompt", system_instruction="sys",
            response_model=DummyModel, max_output_tokens=100,
        )
    assert ok is True
    assert len(items) == 1
    assert "box_2d" not in items[0]


def test_ministry_analyze_tile_markdown_fenced_response():
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k", model="qwen3-vl")
    content = "Here are the violations:\n```json\n" + json.dumps(
        [{"rule_id": "DGA-X", "severity": "Error"}]
    ) + "\n```"
    resp = _mk_response(json_data={"choices": [{"message": {"content": content}}]})
    with patch.object(vp.httpx.Client, "post", return_value=resp):
        items, ok = provider.analyze_tile(
            make_image(), "prompt", system_instruction="sys",
            response_model=DummyModel, max_output_tokens=100,
        )
    assert ok is True
    assert items[0]["rule_id"] == "DGA-X"


def test_ministry_analyze_tile_unparseable_text_is_not_ok():
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k", model="qwen3-vl")
    resp = _mk_response(json_data={"choices": [{"message": {"content": "sorry, I cannot help with that"}}]})
    with patch.object(vp.httpx.Client, "post", return_value=resp):
        items, ok = provider.analyze_tile(
            make_image(), "prompt", system_instruction="sys",
            response_model=DummyModel, max_output_tokens=100,
        )
    assert ok is False
    assert items == []


def test_ministry_analyze_tile_http_error_is_not_ok():
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k", model="qwen3-vl")
    resp = _mk_response(status_code=401, text="unauthorized")
    with patch.object(vp.httpx.Client, "post", return_value=resp):
        items, ok = provider.analyze_tile(
            make_image(), "prompt", system_instruction="sys",
            response_model=DummyModel, max_output_tokens=100,
        )
    assert ok is False
    assert items == []


def test_ministry_analyze_tile_unexpected_json_shape_is_not_ok():
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k", model="qwen3-vl")
    resp = _mk_response(json_data={"unexpected": "shape"})  # no choices[] at all
    with patch.object(vp.httpx.Client, "post", return_value=resp):
        items, ok = provider.analyze_tile(
            make_image(), "prompt", system_instruction="sys",
            response_model=DummyModel, max_output_tokens=100,
        )
    assert ok is False
    assert items == []


def test_ministry_analyze_tile_transport_error_retries_then_gives_up():
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k",
                                          model="qwen3-vl", max_retries=2)
    with patch.object(vp.httpx.Client, "post", side_effect=vp.httpx.ConnectError("boom")) as mock_post:
        with patch("time.sleep"):  # don't actually sleep in tests
            items, ok = provider.analyze_tile(
                make_image(), "prompt", system_instruction="sys",
                response_model=DummyModel, max_output_tokens=100,
            )
    assert ok is False
    assert items == []
    assert mock_post.call_count == 2  # exhausted max_retries, no more


def test_ministry_analyze_tile_transport_error_then_success():
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k",
                                          model="qwen3-vl", max_retries=3)
    ok_resp = _mk_response(json_data={"choices": [{"message": {
        "content": json.dumps([{"rule_id": "DGA-X", "severity": "Error"}])
    }}]})
    with patch.object(vp.httpx.Client, "post",
                       side_effect=[vp.httpx.ConnectError("boom"), ok_resp]):
        with patch("time.sleep"):
            items, ok = provider.analyze_tile(
                make_image(), "prompt", system_instruction="sys",
                response_model=DummyModel, max_output_tokens=100,
            )
    assert ok is True
    assert items[0]["rule_id"] == "DGA-X"


def test_ministry_cache_key_component():
    provider = vp.MinistryVisionProvider(api_base="https://gw.example/v1", api_key="k", model="qwen3-vl")
    assert provider.cache_key_component == "ministry:qwen3-vl"


# ---------------------------------------------------------------- GeminiVisionProvider

def test_gemini_analyze_tile_happy_path():
    provider = vp.GeminiVisionProvider(api_key="fake-key")
    fake_result = MagicMock()
    fake_result.text = json.dumps([{"rule_id": "DGA-X", "severity": "Error", "confidence": "عالية",
                                     "evidence": "ev", "recommendation": "rec", "box_2d": [1, 2, 3, 4]}])
    provider._client.models.generate_content = MagicMock(return_value=fake_result)
    items, ok = provider.analyze_tile(
        make_image(), "prompt", system_instruction="sys",
        response_model=DummyModel, max_output_tokens=100,
    )
    assert ok is True
    assert items[0]["box_2d"] == [1, 2, 3, 4]


def test_gemini_analyze_tile_failure_returns_ok_false_not_raise():
    provider = vp.GeminiVisionProvider(api_key="fake-key")
    provider._client.models.generate_content = MagicMock(side_effect=RuntimeError("boom"))
    items, ok = provider.analyze_tile(
        make_image(), "prompt", system_instruction="sys",
        response_model=DummyModel, max_output_tokens=100,
    )
    assert ok is False
    assert items == []


def test_gemini_cache_key_component():
    provider = vp.GeminiVisionProvider(api_key="fake-key", model="gemini-3.5-flash")
    assert provider.cache_key_component == "gemini:gemini-3.5-flash"


# ---------------------------------------------------------------- get_vision_provider factory

def test_factory_defaults_to_gemini(monkeypatch):
    monkeypatch.delenv("VISION_PROVIDER", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    provider = vp.get_vision_provider()
    assert isinstance(provider, vp.GeminiVisionProvider)


def test_factory_gemini_requires_api_key(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        vp.get_vision_provider()


def test_factory_ministry_selection(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "ministry")
    monkeypatch.setenv("VISION_API_BASE", "https://gw.example/v1")
    monkeypatch.setenv("VISION_MODEL", "qwen3-vl")
    provider = vp.get_vision_provider()
    assert isinstance(provider, vp.MinistryVisionProvider)


def test_factory_ministry_requires_base_and_model(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "ministry")
    monkeypatch.delenv("VISION_API_BASE", raising=False)
    monkeypatch.delenv("VISION_MODEL", raising=False)
    with pytest.raises(RuntimeError):
        vp.get_vision_provider()


def test_factory_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "bogus")
    with pytest.raises(RuntimeError):
        vp.get_vision_provider()


def test_cache_key_id_reflects_backend_and_busts_across_switch(monkeypatch):
    monkeypatch.setenv("VISION_PROVIDER", "ministry")
    monkeypatch.setenv("VISION_MODEL", "qwen3-vl")
    ministry_key = vp.cache_key_id()
    assert ministry_key == "ministry:qwen3-vl"

    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    gemini_key = vp.cache_key_id()
    assert gemini_key == "gemini:gemini-3.5-flash"

    assert ministry_key != gemini_key  # switching backends must bust the tile cache
