import json
from pathlib import Path

def normalize_name(s: str) -> str:
    return (s or "").strip().upper()

def load_roster(path: str="roster.json") -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data

def to_alias(raw: str, roster: dict) -> str:
    key = normalize_name(raw)
    players = roster.get("players", {})
    if key in players:
        return players[key]["alias"]
    # fallback: return raw cleaned
    return raw.strip()

def hand_of(raw: str, roster: dict) -> str:
    key = normalize_name(raw)
    players = roster.get("players", {})
    if key in players:
        return players[key].get("hand","")
    return ""
