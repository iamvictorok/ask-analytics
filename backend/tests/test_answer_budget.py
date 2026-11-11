"""Route mode: every answer must finish inside the DHIS2 Route timeout (max 60 s).

The per-answer LLM budget skips LLM steps once it is used up, and the content
step then falls back to a figures-only answer instead of failing.
"""
import asyncio
import time
import types

import pytest

from backend.app import llm
from backend.app.agent.nodes import generate_content as gc
from backend.config import Settings


@pytest.fixture(autouse=True)
def _reset():
    llm._PRIMARY_DOWN_UNTIL.clear()
    llm.set_deadline(None)
    yield
    llm._PRIMARY_DOWN_UNTIL.clear()
    llm.set_deadline(None)


def _settings(**kw):
    base = dict(llm_provider="gemini", llm_model="gemini/gemini-flash-latest", llm_api_key="k",
                llm_retry_backoff_seconds=0.0, llm_timeout_seconds=40)
    base.update(kw)
    return Settings(**base)


def _resp(text):
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=text))])


def test_budget_defaults_by_mode():
    assert _settings(deployment_mode="route", route_shared_key="x" * 40).effective_answer_budget == 45.0
    assert _settings(deployment_mode="standalone").effective_answer_budget is None
    assert _settings(deployment_mode="route", answer_time_budget_seconds=20).effective_answer_budget == 20.0
    assert _settings(deployment_mode="route", answer_time_budget_seconds=-1).effective_answer_budget is None


def test_no_call_when_budget_used_up(monkeypatch):
    import litellm
    calls = []

    async def fake(**kwargs):
        calls.append(kwargs)
        return _resp("x")

    monkeypatch.setattr(litellm, "acompletion", fake)

    async def go():
        llm.set_deadline(1.0)  # below the minimum needed to start a call
        await llm.complete([{"role": "user", "content": "x"}], _settings())

    with pytest.raises(RuntimeError, match="budget"):
        asyncio.run(go())
    assert calls == []


def test_call_timeout_capped_by_budget(monkeypatch):
    import litellm
    seen = []

    async def fake(**kwargs):
        seen.append(kwargs["timeout"])
        return _resp("ok")

    monkeypatch.setattr(litellm, "acompletion", fake)

    async def go():
        llm.set_deadline(10.0)
        return await llm.complete([{"role": "user", "content": "x"}], _settings())

    assert asyncio.run(go()) == "ok"
    assert seen and seen[0] <= 9.5


def test_hanging_model_stops_at_budget(monkeypatch):
    """A model that never answers must not hold the request past the budget."""
    import litellm

    async def hang(**kwargs):
        await asyncio.sleep(60)

    monkeypatch.setattr(litellm, "acompletion", hang)

    async def go():
        llm.set_deadline(5.0)
        await llm.complete([{"role": "user", "content": "x"}], _settings(llm_transient_retries=2))

    t0 = time.monotonic()
    with pytest.raises(RuntimeError):
        asyncio.run(go())
    assert time.monotonic() - t0 < 6.5


def _state(mode):
    return {
        "session_id": "s",
        "output_mode": mode,
        "requires_data": True,
        "metrics": [{"label": "ANC 1 Coverage", "uid": "Uvn6LCg7dVU", "object_type": "indicator"}],
        "org_unit": {"label": "Sierra Leone"},
        "periods": ["LAST_12_MONTHS"],
        "viz_types": ["bar"],
        "dhis2_data": {
            "headers": ["ou", "pe", "value", "dx"],
            "rows": [["Sierra Leone", "202501", "80.5", "ANC 1 Coverage"],
                     ["Sierra Leone", "202502", "90.25", "ANC 1 Coverage"]],
            "metadata": {},
        },
        "messages": [{"role": "user", "content": "q"}],
    }


@pytest.mark.parametrize("mode", ["report", "conversational"])
def test_content_falls_back_to_figures(monkeypatch, mode):
    async def boom(*a, **k):
        raise RuntimeError("LLM call failed (gemini): answer time budget used up")

    monkeypatch.setattr(gc, "_generate_report", boom)
    monkeypatch.setattr(gc, "_generate_conversational_response", boom)
    state = asyncio.run(gc.generate_content(_state(mode), _settings()))
    text = state.get("active_report_html") if mode == "report" else state.get("active_conversational_response")
    assert gc.FIGURES_ONLY_NOTE in text
    assert "90.25" in text and "80.5" in text


def test_content_without_rows_still_raises(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(gc, "_generate_report", boom)
    st = _state("report")
    st["dhis2_data"]["rows"] = []
    with pytest.raises(RuntimeError):
        asyncio.run(gc.generate_content(st, _settings()))


def test_max_seconds_caps_one_step_and_restores_budget(monkeypatch):
    import litellm
    seen = []

    async def fake(**kwargs):
        seen.append(kwargs["timeout"])
        return _resp("ok")

    monkeypatch.setattr(litellm, "acompletion", fake)

    async def go():
        llm.set_deadline(45.0)
        await llm.complete([{"role": "user", "content": "x"}], _settings(), max_seconds=20)
        left = llm.remaining_budget()
        await llm.complete([{"role": "user", "content": "x"}], _settings())
        return left

    left = asyncio.run(go())
    assert seen[0] <= 10.5          # capped by max_seconds (half kept for the fallback)
    assert seen[1] > 20             # the rest of the 45 s budget is back
    assert left > 40


def test_max_seconds_ignored_without_budget(monkeypatch):
    import litellm
    seen = []

    async def fake(**kwargs):
        seen.append(kwargs["timeout"])
        return _resp("ok")

    monkeypatch.setattr(litellm, "acompletion", fake)
    asyncio.run(llm.complete([{"role": "user", "content": "x"}], _settings(), max_seconds=5))
    assert seen == [40]


def test_budget_switches_model_instead_of_retrying(monkeypatch):
    import litellm
    calls = []

    async def fake(**kwargs):
        calls.append((kwargs["model"], kwargs["timeout"]))
        if kwargs["model"] == "gemini/gemini-flash-latest":
            raise RuntimeError("503 UNAVAILABLE high demand")
        return _resp("lite")

    monkeypatch.setattr(litellm, "acompletion", fake)

    async def go():
        llm.set_deadline(20.0)
        return await llm.complete([{"role": "user", "content": "x"}], _settings(llm_transient_retries=2))

    assert asyncio.run(go()) == "lite"
    assert [m for m, _ in calls] == ["gemini/gemini-flash-latest", "gemini/gemini-flash-lite-latest"]
    assert calls[0][1] <= 10.5      # first model leaves time for the fallback
