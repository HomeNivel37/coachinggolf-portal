import re
from datetime import datetime

# --- Date parsing helpers ----------------------------------------------------

_FRENCH_MONTHS = {
    "janvier": "January", "janv": "Jan", "janv.": "Jan",
    "février": "February", "fevrier": "February", "févr": "Feb", "fevr": "Feb", "févr.": "Feb", "fevr.": "Feb",
    "mars": "Mar",
    "avril": "April", "avr": "Apr", "avr.": "Apr",
    "mai": "May",
    "juin": "Jun",
    "juillet": "July", "juil": "Jul", "juil.": "Jul",
    "août": "Aug", "aout": "Aug",
    "septembre": "September", "sept": "Sep", "sept.": "Sep",
    "octobre": "October", "oct": "Oct", "oct.": "Oct",
    "novembre": "November", "nov": "Nov", "nov.": "Nov",
    "décembre": "December", "decembre": "December", "déc": "Dec", "dec": "Dec", "déc.": "Dec", "dec.": "Dec",
}

_WEEKDAYS_FR = (
    "lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"
)

def _clean_date_string(s: str) -> str:
    s = str(s).strip()

    # Handle Excel "formula-like" strings: ="mercredi, 28 janv. 2026 (20:57)"
    if s.startswith("="):
        s = s.lstrip("=").strip()

    # Strip surrounding quotes
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()

    # Remove parentheses content (time often inside)
    s = re.sub(r"\([^)]*\)", " ", s)

    # Remove weekday prefix "mercredi, "
    lower = s.lower()
    for wd in _WEEKDAYS_FR:
        # "mercredi," or "mercredi"
        if lower.startswith(wd + ","):
            s = s[len(wd)+1:].strip()
            break
        if lower.startswith(wd + " "):
            s = s[len(wd):].strip()
            break

    # Normalize french months → english-ish tokens
    # Replace longer keys first to avoid partial conflicts.
    keys = sorted(_FRENCH_MONTHS.keys(), key=len, reverse=True)
    for k in keys:
        s = re.sub(rf"\b{re.escape(k)}\b", _FRENCH_MONTHS[k], s, flags=re.IGNORECASE)

    # Collapse spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _to_yyyy_mm_dd(value):
    if value is None:
        return None

    # Already a datetime?
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    s = _clean_date_string(value)

    # ISO-like?
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    # Common "DD Mon YYYY" formats (after FR month mapping)
    for fmt in ("%d %b %Y", "%d %B %Y", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    # Regex fallback: capture day, month token, year
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})", s)
    if m:
        d, mon, y = m.groups()
        # Try both abbreviated and full month names
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(f"{int(d)} {mon} {y}", fmt).strftime("%Y-%m-%d")
            except Exception:
                pass

    return None

# --- Public API -------------------------------------------------------------

def session_date_from_csv(df):
    """
    Return session date in YYYY-MM-DD from a dataframe.
    Accepts either 'date' or 'Round Date' (common in Rapsodo exports), plus
    a few variants. Raises a ValueError if none found or unparsable.
    """
    cols = {c.strip().lower(): c for c in df.columns}

    candidates = [
        "date",
        "round date", "round_date", "rounddate",
        "session date", "session_date",
    ]

    col = None
    for k in candidates:
        if k in cols:
            col = cols[k]
            break

    # loose fallback: any column containing 'date'
    if col is None:
        for k, orig in cols.items():
            if "date" in k:
                col = orig
                break

    if col is None:
        raise ValueError("CSV must contain a date column (e.g. 'date' or 'Round Date').")

    series = df[col]
    # first non-null value
    first = None
    for v in series.values:
        if v is not None and str(v).strip() != "" and str(v).strip().lower() != "nan":
            first = v
            break

    dt = _to_yyyy_mm_dd(first)
    if not dt:
        raise ValueError(f"Could not parse session date from column '{col}': {first!r}")
    return dt

def detect_player_name(df, filename: str | None = None):
    """
    Try to detect player name from known columns; otherwise fall back to the filename.
    """
    cols = {c.strip().lower(): c for c in df.columns}
    for key in ["player name", "player", "joueur", "name"]:
        if key in cols:
            v = df[cols[key]].dropna().astype(str).iloc[0].strip()
            if v:
                return v

    # fallback from filename
    if filename:
        base = filename.lower()
        for token in ["licornekeeper", "conre", "treve", "trêve", "sportsman", "cyberman"]:
            if token in base:
                # return canonical base token capitalization (roster handles alias mapping)
                return token

    return "UNKNOWN"
