from __future__ import annotations
from pathlib import Path
import pandas as pd
import numpy as np

def _normalize(s: str) -> str:
    return (s or "").strip().upper()

def _to_alias(raw_name: str, roster: dict) -> str:
    key = _normalize(raw_name)
    players = roster.get("players", {})
    if key in players:
        return players[key]["alias"]
    return raw_name.strip()

def _detect_player(df: pd.DataFrame) -> str:
    for col in ["player", "Player", "Joueur", "joueur", "name", "Name"]:
        if col in df.columns and df[col].dropna().shape[0] > 0:
            v = str(df[col].dropna().iloc[0])
            if v and v.lower() != "nan":
                return v
    return "UNKNOWN"

def _parse_lr_value(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip().upper().replace("°","")
    try:
        return float(s.replace(",", "."))
    except Exception:
        pass
    parts = s.split()
    if len(parts) >= 2:
        try:
            v = float(parts[0].replace(",", "."))
            lr = parts[1]
            if lr.startswith("L"):
                return -v
            if lr.startswith("R"):
                return +v
        except Exception:
            return np.nan
    return np.nan

def _ensure_numeric_lr(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(_parse_lr_value)
    return out

def recompute_spins(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "BackSpin" not in out.columns or "SpinAxis" not in out.columns:
        return out
    axis = pd.to_numeric(out["SpinAxis"], errors="coerce")
    back = pd.to_numeric(out["BackSpin"], errors="coerce")
    axis_rad = np.deg2rad(axis)
    cosv = np.cos(axis_rad).replace(0, np.nan)
    out["SpinTotal"] = back / cosv
    out["SpinLat"] = out["SpinTotal"] * np.sin(axis_rad)
    return out

def generate_all(csv_dfs: list[pd.DataFrame], roster: dict, session_date: str, workdir: str) -> dict:
    """
    Contract expected by app.py (V1.1):

    return {
      'base_xlsx': path,
      'student_pdfs': {alias:[pdf_paths...]},
      'group_pdfs': [pdf_paths...]
    }

    Frozen rules:
    - session_date comes from CSV column 'date' (handled upstream in app.py)
    - alias mapping from roster.json (Conre→Sportsman, Treve/Trêve→Cyberman)
    - Model H must include gapping:
      good shots carry in [Q20;Q95], threshold=20, σ Carry (not variance),
      offline signed+abs, back/lat spin, VLA, peak height, coach text mix analytic+course decision.
    """
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)

    normalized = []
    for df in csv_dfs:
        raw = _detect_player(df)
        alias = _to_alias(raw, roster)
        df2 = df.copy()
        df2["Alias"] = alias
        df2["SessionDate"] = session_date

        df2 = _ensure_numeric_lr(df2, [c for c in ["Offline","HLA","VLA","SpinAxis","DescAngle"] if c in df2.columns])

        for c in ["Carry","TotalDistance","ClubSpeed","BallSpeed","Smash","BackSpin","PeakHeight"]:
            if c in df2.columns:
                df2[c] = pd.to_numeric(df2[c], errors="coerce")

        df2 = recompute_spins(df2)
        normalized.append(df2)

    base_df = pd.concat(normalized, ignore_index=True)

    base_xlsx = work / "Base_Coaching_Golf.xlsx"
    with pd.ExcelWriter(base_xlsx, engine="openpyxl") as writer:
        base_df.to_excel(writer, sheet_name="Shots", index=False)
        sess = (base_df.groupby(["Alias","SessionDate"]).size().reset_index(name="Shots"))
        sess.to_excel(writer, sheet_name="Sessions", index=False)

    ddmmyyyy = session_date.replace("-", "")
    aliases = sorted(base_df["Alias"].dropna().unique())

    # Placeholders: replace with your real models generator
    student_pdfs: dict[str, list[str]] = {}
    for alias in aliases:
        student_pdfs[alias] = []
        for name in ["A","B","C_ELEVE","E","H_ELEVE"]:
            p = work / f"Model{name}_{alias}_{ddmmyyyy}.pdf"
            p.write_bytes(b"%PDF-1.4\n% placeholder\n")
            student_pdfs[alias].append(str(p))

    group_pdfs: list[str] = []
    for name in ["C_GROUPE","D","F","G","H_GROUPE"]:
        p = work / f"Model{name}_GROUPE_{ddmmyyyy}.pdf"
        p.write_bytes(b"%PDF-1.4\n% placeholder\n")
        group_pdfs.append(str(p))

    return {"base_xlsx": str(base_xlsx), "student_pdfs": student_pdfs, "group_pdfs": group_pdfs}
