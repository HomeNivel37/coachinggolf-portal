from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict

def _normalize_name(name: str) -> str:
    """
    Normalize player keys to match roster.json keys:
    - strip
    - lowercase
    - remove accents
    - keep only [a-z0-9]
    """
    if name is None:
        return ""
    s = str(name).strip().lower()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s

def normalize_roster(roster: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure roster has schema:
      {"players": {normalized_key: {"alias": str, "hand": "R"|"L"}, ...}}
    Accepts keys in any case; normalizes them.
    """
    players_in = roster.get("players", {})
    players_out: Dict[str, Dict[str, Any]] = {}

    if isinstance(players_in, dict):
        for raw_key, info in players_in.items():
            key = _normalize_name(raw_key)
            if not key:
                continue
            if isinstance(info, dict):
                alias = str(info.get("alias", raw_key)).strip() or str(raw_key).strip()
                hand = str(info.get("hand", "R")).strip().upper() or "R"
            else:
                alias = str(info).strip() or str(raw_key).strip()
                hand = "R"

            if hand not in ("R", "L"):
                # tolerate right/left
                hl = hand.lower()
                if hl in ("right", "droitier"):
                    hand = "R"
                elif hl in ("left", "gaucher"):
                    hand = "L"
                else:
                    hand = "R"

            players_out[key] = {"alias": alias, "hand": hand}

    roster["players"] = players_out
    return roster

def load_roster(path: str = "roster.json") -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"players": {}}
    roster = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(roster, dict):
        roster = {"players": {}}
    return normalize_roster(roster)

def to_alias(raw_name: str, roster: Dict[str, Any]) -> str:
    key = _normalize_name(raw_name)
    players = roster.get("players", {}) if isinstance(roster, dict) else {}
    if key in players:
        alias = str(players[key].get("alias", "")).strip()
        return alias if alias else str(raw_name).strip()
    return "UNKNOWN"

def hand_of(raw_name: str, roster: Dict[str, Any]) -> str:
    key = _normalize_name(raw_name)
    players = roster.get("players", {}) if isinstance(roster, dict) else {}
    if key in players:
        hand = str(players[key].get("hand", "R")).strip().upper()
        return hand if hand in ("R","L") else "R"
    return "R"

__all__ = ["load_roster","normalize_roster","to_alias","hand_of"]
