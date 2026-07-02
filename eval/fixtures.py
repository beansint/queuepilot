"""Hand-authored edge-case examples for the eval dataset (D2).

These probe *graceful handling*, not label accuracy — they carry no reference labels
(``outputs={}``), so exact-match / label-recall evaluators skip them (return ``None``)
and only the LLM-as-judge / manual inspection cares about their behaviour.
"""

from __future__ import annotations

from eval.dataset import EvalExample

#: A realistic support ticket body, repeated to pad the "very-long" fixture near
#: ``app.config.Settings.max_input_chars`` (8000) without tripping the request-size limit.
_LONG_TICKET_PARAGRAPH = (
    "Our production checkout flow started failing intermittently for a subset of "
    "customers around 14:00 UTC. The error appears to correlate with a recent deploy "
    "of the payment-gateway service, though our rollback did not fully resolve it. "
    "Customers report a spinner that never resolves, followed by a generic 'something "
    "went wrong' message. We have retried on multiple browsers and devices with the "
    "same result. Server logs show intermittent 502s from the gateway, but not on "
    "every request, which makes this hard to reproduce locally. "
)

EDGE_CASES: list[EvalExample] = [
    EvalExample(
        id="edge-near-empty",
        inputs={"text": "hi", "metadata": {"source": "edge"}},
        outputs={},
        source="edge",
    ),
    EvalExample(
        id="edge-ambiguous",
        inputs={
            "text": "it's broken, please fix",
            "metadata": {"source": "edge"},
        },
        outputs={},
        source="edge",
    ),
    EvalExample(
        id="edge-multi-issue",
        inputs={
            "text": (
                "Subject: Two problems today\n\n"
                "First, my invoice from last month shows the wrong tax rate and I need "
                "a corrected copy sent to accounting. Separately, the mobile app keeps "
                "crashing every time I open the settings screen on Android 14 — it "
                "worked fine last week. Please advise on both."
            ),
            "metadata": {"source": "edge"},
        },
        outputs={},
        source="edge",
    ),
    EvalExample(
        id="edge-very-long",
        inputs={
            "text": (
                "Subject: Intermittent checkout failures since today's deploy\n\n"
                + (_LONG_TICKET_PARAGRAPH * 20)
            )[:6900],
            "metadata": {"source": "edge"},
        },
        outputs={},
        source="edge",
    ),
]
