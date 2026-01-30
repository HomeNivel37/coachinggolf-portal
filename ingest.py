import pandas as pd
import numpy as np
from dateutil import parser

def parse_date_column(series: pd.Series) -> pd.Series:
    def _parse(x):
        if pd.isna(x): return pd.NaT
        try:
            return parser.parse(str(x))
        except Exception:
            return pd.NaT
    return series.apply(_parse)
import re
from datetime import datetime

def _to_yyyy_mm_dd(x) -> str:
s = str(x).strip()
if not s:
return ""
# essaie plusieurs formats courants
for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y"):
try:
return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
except Exception:
pass
# fallback: tente extraction ISO dans le texte
m = re.search(r"(20\d{2}[-/]\d{2}[-/]\d{2})", s)
if m:
return m.group(1).replace("/", "-")
return ""

def session_date_from_csv(df, filename: str | None = None):
# noms possibles trouvés dans les exports
candidates = ["date", "Date", "Round Date", "RoundDate", "Session Date", "SessionDate"]
for col in candidates:
if col in df.columns:
d = _to_yyyy_mm_dd(df[col].iloc[0])
if d:
return d

# fallback nom de fichier (si besoin)
if filename:
m = re.search(r"(20\d{2}-\d{2}-\d{2})", filename)
if m:
return m.group(1)

# dernier recours
return datetime.today().strftime("%Y-%m-%d")

# ---- change 290126 date round par section au dessus
#    def session_date_from_csv(df: pd.DataFrame) -> str:
#    if "date" not in df.columns:
#        raise ValueError("CSV must contain a 'date' column.")
#    dt = parse_date_column(df["date"])
#    d = dt.dt.date.dropna()
#    if d.empty:
#        raise ValueError("No valid values found in CSV 'date' column.")
#    # dominant date (mode). If mixed, fall back to median date.
#    vc = d.value_counts()
#    top_date = vc.index[0]
#    if vc.iloc[0] / vc.sum() >= 0.80:
#        return top_date.isoformat()
#    # median date for robustness
#    d_sorted = sorted(d.tolist())
#    return d_sorted[len(d_sorted)//2].isoformat()


def normalize_numeric_fields(df: pd.DataFrame) -> pd.DataFrame:
    # Keep user's existing parsing rules in your generator; here we only ensure columns exist.
    return df

def detect_player_name(df: pd.DataFrame, fallback_filename: str="") -> str:
    # Prefer an explicit column if present
    for col in ["player","Player","Joueur","joueur","name","Name"]:
        if col in df.columns:
            v = str(df[col].dropna().iloc[0])
            if v and v.lower() != "nan":
                return v
    # else try filename pattern <Name>Shots...
    if "Shots" in fallback_filename:
        return fallback_filename.split("Shots")[0]
    return fallback_filename.replace(".csv","")
