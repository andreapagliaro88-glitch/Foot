"""
utils.py — Helper functions: goal timing parser, formatters
"""

import base64
import json
import math
import mimetypes
import os
import re


def parse_goal_minute_value(token) -> int | None:
    """
    Parse a single goal-minute token into an integer minute.
    Returns None for empty / invalid values.

    Supported formats:
    - "32"     -> 32
    - "45+2"   -> 47
    - "90'4"   -> 94
    - "45'2"   -> 47
    """
    if token is None:
        return None
    try:
        if math.isnan(float(token)):
            return None
    except (ValueError, TypeError):
        pass

    s = str(token).strip().replace(" ", "")
    if not s or s.lower() == "nan":
        return None

    m = re.match(r"^(\d+)[''](\d+)$", s)
    if m:
        return int(m.group(1)) + int(m.group(2))

    if "+" in s:
        base_s, extra_s = s.split("+", 1)
        try:
            base = int(base_s)
            extra = int(extra_s) if extra_s else 0
            return base + extra
        except ValueError:
            return None

    try:
        minute = int(float(s))
        return minute if minute > 0 else None
    except ValueError:
        return None


def parse_minutes(timing_str) -> list:
    """Parse one CSV timing column -> list of minute ints (invalid tokens skipped)."""
    return [minute for minute, _ in parse_goal_timings(timing_str)]


def get_all_goals(home_str, away_str) -> list:
    """Merge home + away goal minutes, sort ascending."""
    goals = parse_minutes(home_str) + parse_minutes(away_str)
    goals.sort()
    return goals


def get_first_goal(home_str, away_str):
    """Return minute of the first goal in the match, or None if no goals."""
    goals = get_all_goals(home_str, away_str)
    return goals[0] if goals else None


def get_sorted_goals_with_team(home_str, away_str):
    """All goals sorted by minute: [(minute, 'home'|'away'), ...]."""
    goals = [(m, "home") for m in parse_minutes(home_str)]
    goals += [(m, "away") for m in parse_minutes(away_str)]
    goals.sort(key=lambda x: x[0])
    return goals


def get_first_and_after(home_str, away_str):
    """Return (first_goal_minute, list_of_minutes_after) or (None, [])."""
    goals = get_sorted_goals_with_team(home_str, away_str)
    if not goals:
        return None, []
    first = goals[0][0]
    after = [m for m, _ in goals[1:]]
    return first, after


def get_first_goal_with_team(home_str, away_str):
    """Return (minute, team) for the first goal — team is 'home' or 'away'."""
    goals = get_sorted_goals_with_team(home_str, away_str)
    return goals[0] if goals else None


def get_first_goal_detail(home_str, away_str):
    """Return (first_minute, team, all_goal_minutes) or (None, None, [])."""
    goals = get_sorted_goals_with_team(home_str, away_str)
    if not goals:
        return None, None, []
    first_min, team = goals[0]
    all_goals = [m for m, _ in goals]
    return first_min, team, all_goals


def parse_goal_timings(timing_str) -> list:
    """
    Input:  "37,90'4,49,88"  or  "64,76"  or  nan / empty / None
    Output: list of (minute, original_token) tuples — invalid tokens skipped.
    """
    if timing_str is None:
        return []
    try:
        if math.isnan(float(timing_str)):
            return []
    except (ValueError, TypeError):
        pass

    timing_str = str(timing_str).strip()
    if not timing_str or timing_str.lower() == "nan":
        return []

    results = []
    for token in [t.strip() for t in timing_str.split(",") if t.strip()]:
        minute = parse_goal_minute_value(token)
        if minute is not None:
            results.append((minute, token))
    return results


def get_first_goal_from_timings(home_timings_str, away_timings_str) -> dict | None:
    """
    First goal from CSV timing columns (merge both teams, sort, take minimum).

    Example:
        home = "41,54,60", away = "32,50,59"
        -> {"minute": 32, "team": "away", "token": "32", "is_home": 0}
    """
    first = get_first_goal_with_team(home_timings_str, away_timings_str)
    if not first:
        return None
    minute, team = first
    return {
        "minute": minute,
        "team": team,
        "token": str(minute),
        "is_home": 1 if team == "home" else 0,
    }


def get_first_goal_from_events(events: list) -> dict | None:
    """First goal from goal_events rows (same merge + min logic as CSV timings)."""
    all_goals = []
    for e in events or []:
        minute = parse_goal_minute_value(e.get("minute"))
        if minute is None:
            continue
        is_home = e.get("is_home", 0)
        team = "home" if is_home == 1 else "away"
        all_goals.append((minute, team, e.get("minute")))

    if not all_goals:
        return None

    all_goals.sort(key=lambda x: x[0])
    minute, team, raw = all_goals[0]
    return {
        "minute": minute,
        "team": team,
        "token": str(raw) if raw is not None else str(minute),
        "is_home": 1 if team == "home" else 0,
    }


def get_half(minute: int, original_token: str = "") -> int:
    """
    Determines which half a goal belongs to.

    - "45'x" / "45+x" → half 1 (recupero 1° tempo)
    - "90'x" / "90+x" → half 2 (recupero 2° tempo)
    - plain minute 1-45  → half 1
    - plain minute 46+   → half 2
    """
    token_str = str(original_token).strip()
    if "'" in token_str:
        try:
            base = int(token_str.split("'")[0])
            return 1 if base == 45 else 2
        except ValueError:
            pass
    if "+" in token_str:
        try:
            base = int(token_str.split("+")[0])
            if base == 45:
                return 1
            if base >= 90:
                return 2
        except ValueError:
            pass
    return 1 if minute <= 45 else 2


def is_stoppage_goal(minute: int, original_token: str = "", half: int | None = None) -> bool:
    """True se il gol è in recupero 1T (45+) o 2T (90+)."""
    token_str = str(original_token).strip()
    if "'" in token_str:
        try:
            base = int(token_str.split("'")[0])
            return base == 45 or base >= 90
        except ValueError:
            pass
    if "+" in token_str:
        try:
            base = int(token_str.split("+")[0])
            return base == 45 or base >= 90
        except ValueError:
            pass
    h = half if half is not None else get_half(minute, original_token)
    return (h == 1 and minute > 45) or (h == 2 and minute > 90)


def format_pct(value) -> str:
    """Returns '63.4%' formatted string. Handles None/NaN gracefully."""
    try:
        if value is None or math.isnan(float(value)):
            return "N/A"
        return f"{float(value):.1f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_roi(value) -> str:
    """Returns '+12.3%' or '-8.1%' with sign. Handles None/NaN gracefully."""
    try:
        if value is None or math.isnan(float(value)):
            return "N/A"
        v = float(value)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.1f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_num(value, decimals: int = 2) -> str:
    """Generic number formatter."""
    try:
        if value is None or math.isnan(float(value)):
            return "N/A"
        return f"{float(value):.{decimals}f}"
    except (ValueError, TypeError):
        return "N/A"


def get_pct_color(value) -> str:
    """
    Strict dynamic color threshold rule:
      Red    (#ef4444): 0.0%  – 50.0%
      Orange (#f59e0b): 50.1% – 69.99%
      Green  (#22c55e): 70.0% – 100.0%

    Accepts both raw floats (e.g. 63.4) and string percentages (e.g. '63.4%').
    Returns white (#ffffff) if the value cannot be parsed.
    """
    try:
        float_val = float(str(value).replace('%', '').strip())
        if float_val <= 50.0:
            return "#ef4444"   # Red
        elif float_val < 70.0:
            return "#f59e0b"   # Orange
        else:
            return "#22c55e"   # Green
    except (ValueError, TypeError):
        return "#ffffff"       # Default white


# ── Team logos (data/team_logos.json + assets/teams/) ───────────────────────

_PROJECT_ROOT = os.path.dirname(__file__)
_LOGOS_JSON = os.path.join(_PROJECT_ROOT, "data", "team_logos.json")
_TEAM_LOGOS_CACHE: dict | None = None
_URL_DATA_CACHE: dict[str, str] = {}


def _normalize_team_key(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def _load_team_logos() -> dict:
    global _TEAM_LOGOS_CACHE
    if _TEAM_LOGOS_CACHE is not None:
        return _TEAM_LOGOS_CACHE
    if not os.path.isfile(_LOGOS_JSON):
        _TEAM_LOGOS_CACHE = {}
        return _TEAM_LOGOS_CACHE
    with open(_LOGOS_JSON, encoding="utf-8") as f:
        raw = json.load(f)
    _TEAM_LOGOS_CACHE = {
        _normalize_team_key(k): v
        for k, v in raw.items()
        if not str(k).startswith("_") and isinstance(v, dict)
    }
    return _TEAM_LOGOS_CACHE


def reload_team_logos():
    """Ricarica la mappa loghi (es. dopo modifica al JSON)."""
    global _TEAM_LOGOS_CACHE
    _TEAM_LOGOS_CACHE = None
    _URL_DATA_CACHE.clear()
    return _load_team_logos()


def _read_team_logos_file() -> dict:
    if not os.path.isfile(_LOGOS_JSON):
        return {
            "_comment": "Mappa nome squadra (come nel DB) → logo. Usa url e/o local.",
        }
    with open(_LOGOS_JSON, encoding="utf-8") as f:
        return json.load(f)


def team_logo_slug(team_name: str) -> str:
    import unicodedata
    ascii_name = unicodedata.normalize("NFKD", str(team_name))
    ascii_name = ascii_name.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "team"


def save_team_logos_file(data: dict) -> None:
    os.makedirs(os.path.dirname(_LOGOS_JSON), exist_ok=True)
    with open(_LOGOS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    reload_team_logos()


def upsert_team_logo(team_name: str, url: str = "", local: str = "") -> None:
    """Aggiorna o crea entry logo per una squadra."""
    data = _read_team_logos_file()
    data[team_name] = {
        "url": str(url or "").strip(),
        "local": str(local or "").strip(),
    }
    save_team_logos_file(data)


def remove_team_logo(team_name: str) -> bool:
    data = _read_team_logos_file()
    if team_name not in data:
        return False
    del data[team_name]
    save_team_logos_file(data)
    return True


def save_team_logo_bytes(team_name: str, file_bytes: bytes, filename: str) -> str:
    """Salva immagine in assets/teams/ e ritorna path relativo."""
    ext = os.path.splitext(filename)[1].lower() or ".png"
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        ext = ".png"
    folder = os.path.join(_PROJECT_ROOT, "assets", "teams")
    os.makedirs(folder, exist_ok=True)
    rel = f"assets/teams/{team_logo_slug(team_name)}{ext}"
    full = os.path.join(_PROJECT_ROOT, rel)
    with open(full, "wb") as f:
        f.write(file_bytes)
    return rel


def list_configured_team_logos() -> dict[str, dict]:
    data = _read_team_logos_file()
    return {k: v for k, v in data.items() if not str(k).startswith("_") and isinstance(v, dict)}


def get_team_logo_entry(team_name: str) -> dict | None:
    if not team_name:
        return None
    logos = _load_team_logos()
    entry = logos.get(_normalize_team_key(team_name))
    if entry:
        return entry
    norm = _normalize_team_key(team_name)
    for key, val in logos.items():
        if key in norm or norm in key:
            return val
    return None


def _bytes_to_data_uri(data: bytes, mime: str = "image/png") -> str:
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _local_logo_to_data_uri(path: str) -> str | None:
    if not path:
        return None
    full = path if os.path.isabs(path) else os.path.join(_PROJECT_ROOT, path)
    if not os.path.isfile(full):
        return None
    mime, _ = mimetypes.guess_type(full)
    if not mime:
        mime = "image/png"
    with open(full, "rb") as img:
        return _bytes_to_data_uri(img.read(), mime)


def _url_to_data_uri(url: str) -> str | None:
    """Scarica il logo e lo incorpora in base64 (Streamlit blocca spesso URL esterni in HTML)."""
    if not url:
        return None
    if url in _URL_DATA_CACHE:
        return _URL_DATA_CACHE[url]
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = resp.read()
            ctype = resp.headers.get_content_type()
        if not ctype or not ctype.startswith("image/"):
            ctype = "image/png"
        embedded = _bytes_to_data_uri(data, ctype)
        _URL_DATA_CACHE[url] = embedded
        return embedded
    except Exception:
        return None


def get_team_logo_src(team_name: str) -> str | None:
    """Data-URI incorporato per <img src> (compatibile con st.html)."""
    entry = get_team_logo_entry(team_name)
    if not entry:
        return None
    url = str(entry.get("url") or "").strip()
    if url.startswith(("http://", "https://")):
        embedded = _url_to_data_uri(url)
        if embedded:
            return embedded
    local = str(entry.get("local") or "").strip()
    if local:
        local_uri = _local_logo_to_data_uri(local)
        if local_uri:
            return local_uri
    return None


def team_initials(team_name: str) -> str:
    parts = [p for p in str(team_name).split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return str(team_name)[:2].upper()


def team_logo_html(
    team_name: str,
    size: int = 52,
    fallback_color: str = "#334155",
    show_name: bool = True,
    name_color: str = "#f1f5f9",
) -> str:
    """Logo nudo se configurato, cerchio con iniziali altrimenti."""
    src = get_team_logo_src(team_name)
    if src:
        circle = (
            f'<img src="{src}" alt="{team_name}" '
            f'style="width:{size}px;height:{size}px;object-fit:contain;display:block;" />'
        )
    else:
        init = team_initials(team_name)
        fsize = "13px" if len(init) > 2 else "15px"
        circle = (
            f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
            f'background:{fallback_color};display:flex;align-items:center;'
            f'justify-content:center;font-weight:900;font-size:{fsize};color:#fff;'
            f'border:2px solid rgba(255,255,255,0.15);">'
            f'{init}</div>'
        )
    name_block = ""
    if show_name:
        name_block = (
            f'<div style="font-size:13px;font-weight:800;color:{name_color};'
            f'margin-top:6px;text-align:center;">{team_name}</div>'
        )
    return (
        f'<div style="display:flex;flex-direction:column;align-items:center;">'
        f'{circle}{name_block}</div>'
    )


def build_league_name(country: str, championship: str) -> str:
    """Combina nazione e campionato nel formato usato dal DB (es. Argentina - Primera B)."""
    country = (country or "").strip()
    championship = (championship or "").strip()
    if not country or not championship:
        return ""
    return f"{country} - {championship}"


def split_league_name(league: str) -> tuple[str, str]:
    """Separa 'Nazione - Campionato' in (nazione, campionato)."""
    league = (league or "").strip()
    if " - " in league:
        country, name = league.split(" - ", 1)
        return country.strip(), name.strip()
    return league, league