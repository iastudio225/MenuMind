"""In-memory, per-process AI quotas by restaurant (D1.22).

Scope and honesty notes:
- Counters live in process memory: each backend process enforces its own
  budget. With several workers the effective limit is multiplied — this is a
  best-effort protection, not a global quota. No Redis/dependency is added.
- Keys are server-side restaurant ids and timestamps only: no prompts, no
  conversations, no customer data, no API keys ever stored or logged here.
- Window is a 60s sliding window; expired entries are pruned on access and a
  global purge bounds memory even for restaurants never seen again.

Distinct notions:
- request rate  : messages accepted per window per restaurant (frequency);
- model usage   : provider.generate calls per window per restaurant;
- real money cost cannot be derived from these counters alone (tariffs,
  models and billing data are external).
"""
import time
from typing import Dict, List

from fastapi import HTTPException

WINDOW_S = 60.0
MAX_REQUESTS_PER_RESTAURANT = 10     # messages / window / restaurant
MAX_MODEL_CALLS_PER_RESTAURANT = 60  # model calls / window / restaurant
_MAX_KEYS = 5000                     # global purge threshold per counter

_requests: Dict[str, List[float]] = {}
_model_calls: Dict[str, List[float]] = {}

GENERIC_429 = "Trop de requêtes. Patientez un instant."


def _prune(counter: Dict[str, List[float]], now: float) -> None:
    """Drop expired entries everywhere and remove dead keys (bounded memory)."""
    dead = []
    for k, hits in counter.items():
        fresh = [t for t in hits if now - t < WINDOW_S]
        if fresh:
            counter[k] = fresh
        else:
            dead.append(k)
    for k in dead:
        del counter[k]


def _slot(counter: Dict[str, List[float]], key: str, limit: int, now: float) -> None:
    if len(counter) >= _MAX_KEYS:
        _prune(counter, now)
    hits = [t for t in counter.get(key, ()) if now - t < WINDOW_S]
    if len(hits) >= limit:
        raise HTTPException(status_code=429, detail=GENERIC_429)
    hits.append(now)
    counter[key] = hits


def check_request(restaurant_id: str) -> None:
    """Raise 429 when the restaurant already consumed its message budget."""
    _slot(_requests, restaurant_id, MAX_REQUESTS_PER_RESTAURANT, time.time())


def record_model_call(restaurant_id: str) -> None:
    """Reserve one model call for this restaurant; raise 429 when exhausted.

    Called before each provider.generate so a refused request never reaches
    the model. The counter holds timestamps only.
    """
    _slot(_model_calls, restaurant_id, MAX_MODEL_CALLS_PER_RESTAURANT, time.time())


def reset() -> None:
    """Test helper: clear all counters."""
    _requests.clear()
    _model_calls.clear()
