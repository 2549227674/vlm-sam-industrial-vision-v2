"""Retry logic contract tests for simulator/line_runner.py post_with_retry().

Tests the CLIENT-SIDE retry behavior (not the backend).
"""

from unittest.mock import MagicMock, patch

from simulator.line_runner import MAX_RETRIES, post_with_retry


def _make_meta():
    return {
        "line_id": "L1",
        "category": "metal_nut",
        "defect_type": "scratch",
        "severity": "high",
        "confidence": 0.95,
        "anomaly_score": 12.5,
        "bboxes": [],
        "description": "test",
        "variant": "2B_base",
        "edge_ts": "2026-05-09T00:00:00+00:00",
        "pipeline_ms": {"efficientad": 10.0, "fastsam": 40.0, "qwen3vl": 500.0},
        "vlm_metrics": {
            "ttft_ms": 300.0,
            "decode_tps": 12.0,
            "prompt_tokens": 800,
            "output_tokens": 40,
            "rss_mb": 2800.0,
            "json_parse_ok": True,
        },
        "schema_version": "v1",
    }


@patch("simulator.line_runner.time.sleep")
def test_exhausts_retries_on_persistent_503(mock_sleep):
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=503)

    post_with_retry(session, "L1", "2B_base", b"img", "f.jpg", _make_meta())
    assert session.post.call_count == MAX_RETRIES + 1


@patch("simulator.line_runner.time.sleep")
def test_retries_then_succeeds_on_200(mock_sleep):
    session = MagicMock()
    session.post.side_effect = [
        MagicMock(status_code=503),
        MagicMock(status_code=503),
        MagicMock(status_code=200, json=lambda: {"id": 1}),
    ]

    post_with_retry(session, "L1", "2B_base", b"img", "f.jpg", _make_meta())
    assert session.post.call_count == 3


@patch("simulator.line_runner.time.sleep")
def test_no_retry_on_400(mock_sleep):
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=400, text="bad request")

    post_with_retry(session, "L1", "2B_base", b"img", "f.jpg", _make_meta())
    assert session.post.call_count == 1


@patch("simulator.line_runner.time.sleep")
def test_exponential_backoff_sleep_called(mock_sleep):
    session = MagicMock()
    session.post.return_value = MagicMock(status_code=503)

    post_with_retry(session, "L1", "2B_base", b"img", "f.jpg", _make_meta())

    sleep_values = [call.args[0] for call in mock_sleep.call_args_list]
    assert len(sleep_values) == MAX_RETRIES
    # base=500ms: attempt0→500+rand, attempt1→1000+rand, attempt2→2000+rand ...
    for i, val in enumerate(sleep_values):
        base_ms = 500 * (2 ** i)
        assert val >= base_ms / 1000.0  # at least the base (without jitter)


@patch("simulator.line_runner.time.sleep")
def test_network_exception_retries(mock_sleep):
    import requests

    session = MagicMock()
    session.post.side_effect = [
        requests.exceptions.ConnectionError("timeout"),
        MagicMock(status_code=200, json=lambda: {"id": 1}),
    ]

    post_with_retry(session, "L1", "2B_base", b"img", "f.jpg", _make_meta())
    assert session.post.call_count == 2
