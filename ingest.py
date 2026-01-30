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

def session_date_from_csv(df: pd.DataFrame) -> str:
    if "date" not in df.columns:
        raise ValueError("CSV must contain a 'date' column.")
    dt = parse_date_column(df["date"])
    d = dt.dt.date.dropna()
    if d.empty:
        raise ValueError("No valid values found in CSV 'date' column.")
    # dominant date (mode). If mixed, fall back to median date.
    vc = d.value_counts()
    top_date = vc.index[0]
    if vc.iloc[0] / vc.sum() >= 0.80:
        return top_date.isoformat()
    # median date for robustness
    d_sorted = sorted(d.tolist())
    return d_sorted[len(d_sorted)//2].isoformat()

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
