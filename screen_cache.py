"""
screen_cache.py — Cache analisi per pagina (Prematch / Live)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

import pandas as pd
import streamlit as st

from database import get_goal_events_for_matches, get_matches_dataframe
from filters import apply_filters


def filters_fingerprint(screen: str, filters: dict, extra: dict | None = None) -> str:
    skip = {"_apply", "_top_analyze", "goal_time_errors"}
    payload = {
        k: v for k, v in sorted(filters.items())
        if k not in skip and not str(k).startswith("_")
    }
    if extra:
        payload["_extra"] = extra
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.md5(f"{screen}:{raw}".encode()).hexdigest()


def _store_get(namespace: str, key: str) -> Any | None:
    store = st.session_state.setdefault(namespace, {})
    return store.get(key)


def _store_set(namespace: str, key: str, value: Any, max_entries: int = 4) -> Any:
    store = st.session_state.setdefault(namespace, {})
    store[key] = value
    while len(store) > max_entries:
        store.pop(next(iter(store)))
    return value


def load_prematch_data(filters: dict, compute_fn: Callable[[], dict]) -> dict:
    key = filters_fingerprint("prematch", filters)
    cached = _store_get("_pm_data", key)
    if cached is not None:
        return cached
    return _store_set("_pm_data", key, compute_fn())


def load_live_data(filters: dict, extra: dict, compute_fn: Callable[[], dict]) -> dict:
    key = filters_fingerprint("live", filters, extra)
    cached = _store_get("_live_data", key)
    if cached is not None:
        return cached
    return _store_set("_live_data", key, compute_fn())


def build_prematch_frame(filters: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict, list[int]]:
    df = get_matches_dataframe()
    if df.empty:
        return df, df, {}, []
    filtered = apply_filters(df, filters)
    if filtered.empty:
        return df, filtered, {}, []
    match_ids = list(filtered["match_id"].dropna().astype(int))
    goal_events = get_goal_events_for_matches(match_ids)
    return df, filtered, goal_events, match_ids
