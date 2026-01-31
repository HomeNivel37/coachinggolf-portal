from __future__ import annotations

from pathlib import Path
import math
import re
from typing import Dict, List, Any

import numpy as np
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from models.modelA_gold import build_modelA_gold
from models.modelB_gold import build_modelB_gold
from models.modelC_gold import build_modelC_gold
from models.modelD_gold import build_modelD_gold

from ingest import detect_player_name
from roster import to_alias, hand_of


# ----------------------------
# Parsing helpers
# ----------------------------
def _parse_lr(x):
    """
    Parse signed values encoded as:
      "20 L" => -20
      "15 R" => +15
      "10"   => 10
      "-5"   => -5
    """
    if pd.isna(x):
        return np.nan
    s = str(x).strip().upper().replace("°", "")
    if not s or s == "NAN":
        return np.nan

    # direct number
    try:
        return float(s.replace(",", "."))
    except Exception:
        pass

    m = re.match(r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*([LR])\s*$", s)
    if m:
        v = float(m.group(1).replace(",", "."))
        lr = m.group(2)
        return -v if lr == "L" else +v

    # sometimes "20L" no space
    m2 = re.match(r"^\s*([+-]?\d+(?:[.,]\d+)?)([LR])\s*$", s)
    if m2:
        v = float(m2.group(1).replace(",", "."))
        lr = m2.group(2)
        return -v if lr == "L" else +v

    return np.nan


def _coerce_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def _coerce_lr(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = out[c].apply(_parse_lr)
    return out


def _club_col(df: pd.DataFrame) -> str | None:
    for c in ["Club Name", "Club", "club", "ClubName"]:
        if c in df.columns:
            return c
    return None


def _is_driver_series(df: pd.DataFrame) -> pd.Series:
    ccol = _club_col(df)
    if ccol is None:
        return pd.Series([False] * len(df), index=df.index)
    s = df[ccol].astype(str).str.upper().fillna("")
    return s.str.startswith("DR") | s.str.contains("DRIVER")


def recompute_spins(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute SpinTotal and SpinLat (rpm) from BackSpin and SpinAxis (deg).
    SpinTotal = BackSpin / cos(axis)
    SpinLat   = SpinTotal * sin(axis)
    """
    out = df.copy()
    if "BackSpin" not in out.columns or "SpinAxis" not in out.columns:
        return out

    back = pd.to_numeric(out["BackSpin"], errors="coerce")
    axis = pd.to_numeric(out["SpinAxis"], errors="coerce")
    axis_rad = np.deg2rad(axis)

    cosv = np.cos(axis_rad)
    cosv = cosv.replace(0, np.nan)

    spin_total = back / cosv
    spin_lat = spin_total * np.sin(axis_rad)

    out["SpinTotal"] = spin_total
    out["SpinLat"] = spin_lat
    return out


# ----------------------------
# PDF helpers (valid PDFs)
# ----------------------------
def _simple_pdf(path: str, title: str, lines: List[str]):
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    y = h - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, title)
    y -= 32
    c.setFont("Helvetica", 11)
    for line in lines:
        if y < 72:
            c.showPage()
            y = h - 72
            c.setFont("Helvetica", 11)
        c.drawString(72, y, line[:110])
        y -= 16
    c.showPage()
    c.save()


# ----------------------------
# Main entry
# ----------------------------
def generate_all(csv_dfs: List[pd.DataFrame], roster: Dict[str, Any], session_date: str, workdir: str) -> Dict[str, Any]:
    """
    Returns:
      {
        "base_xlsx": "...",
        "student_pdfs": {alias:[...pdfs...]},
        "group_pdfs": [...pdfs...]
      }
    """
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)

    shots_frames = []
    for df in csv_dfs:
        # try filename from attrs if app provides it
        src_name = df.attrs.get("source_name") or df.attrs.get("filename")
        raw = detect_player_name(df, src_name)
        alias = to_alias(raw, roster)
        hand = hand_of(raw, roster)

        df2 = df.copy()

        # Rename common columns into canonical names if needed
        ren = {}
        if "Carry" not in df2.columns:
            for c in ["Carry Dist (m)", "Carry (m)", "CarryDistance", "Carry Distance"]:
                if c in df2.columns:
                    ren[c] = "Carry"
        if "Offline" not in df2.columns:
            for c in ["Offline (m)", "offline"]:
                if c in df2.columns:
                    ren[c] = "Offline"
        if "BackSpin" not in df2.columns:
            for c in ["Back Spin", "Backspin", "Spin Back", "Back Spin (rpm)"]:
                if c in df2.columns:
                    ren[c] = "BackSpin"
        if "SpinAxis" not in df2.columns:
            for c in ["Spin Axis", "Spin axis", "SpinAxis (deg)"]:
                if c in df2.columns:
                    ren[c] = "SpinAxis"
        if "Smash" not in df2.columns:
            for c in ["Smash Factor", "SmashFactor"]:
                if c in df2.columns:
                    ren[c] = "Smash"
        if "ClubSpeed" not in df2.columns:
            for c in ["Club Speed", "Club Speed (mph)"]:
                if c in df2.columns:
                    ren[c] = "ClubSpeed"
        if "BallSpeed" not in df2.columns:
            for c in ["Ball Speed", "Ball Speed (mph)"]:
                if c in df2.columns:
                    ren[c] = "BallSpeed"
        if "VLA" not in df2.columns:
            for c in ["VLA (deg)", "Vertical Launch Angle", "Vert Launch Angle"]:
                if c in df2.columns:
                    ren[c] = "VLA"
        if "HLA" not in df2.columns:
            for c in ["HLA (deg)", "Horizontal Launch Angle", "Hor Launch Angle"]:
                if c in df2.columns:
                    ren[c] = "HLA"
        if "PeakHeight" not in df2.columns:
            for c in ["Peak Height", "Peak Height (m)", "peak height"]:
                if c in df2.columns:
                    ren[c] = "PeakHeight"

        if ren:
            df2 = df2.rename(columns=ren)

        # signed textual columns
        df2 = _coerce_lr(df2, [c for c in ["Offline","HLA","VLA","SpinAxis"] if c in df2.columns])

        # numeric columns
        df2 = _coerce_numeric(df2, [c for c in ["Carry","BackSpin","Smash","ClubSpeed","BallSpeed","PeakHeight"] if c in df2.columns])
        # Compute Smash if not provided in CSV: Smash = BallSpeed / ClubSpeed (mph/mph)
        if ("Smash" not in df2.columns) or (df2["Smash"].isna().all() if "Smash" in df2.columns else True):
            if "BallSpeed" in df2.columns and "ClubSpeed" in df2.columns:
                df2["Smash_raw"] = df2["BallSpeed"] / df2["ClubSpeed"]
                df2["Smash_raw"] = df2["Smash_raw"].replace([np.inf, -np.inf], np.nan)
                df2["Smash"] = df2["Smash_raw"].clip(lower=0, upper=1.50)


        # recompute spins
        df2 = recompute_spins(df2)

        # flags / meta
        df2["SessionDate"] = session_date
        df2["PlayerRaw"] = raw
        df2["Alias"] = alias
        df2["Hand"] = hand
        df2["IsDriver"] = _is_driver_series(df2)

        shots_frames.append(df2)

    shots = pd.concat(shots_frames, ignore_index=True) if shots_frames else pd.DataFrame()

    # Sessions summary: per player
    sessions_rows = []
    if not shots.empty:
        for alias, g in shots.groupby("Alias"):
            clubs_played = g[_club_col(g)].nunique() if _club_col(g) else np.nan
            # Driver fairway count: driver shots with |offline|<=20 AND carry>=130 (best for "bons drives")
            if "Carry" in g.columns and "Offline" in g.columns:
                mask = (g["IsDriver"] == True) & (g["Offline"].abs() <= 20)
                fair_cnt = int(mask.sum())
            else:
                fair_cnt = 0

            # Driver average carry for "bons drives": carry > 120 m
            if "Carry" in g.columns:
                drv_good = g[(g["IsDriver"] == True) & (g["Carry"] > 120)]
                drv_avg_carry_gt120 = float(drv_good["Carry"].mean()) if len(drv_good) else float("nan")
                drv_cnt_gt120 = int(len(drv_good))
            else:
                drv_avg_carry_gt120 = float("nan")
                drv_cnt_gt120 = 0

            sessions_rows.append({
                "SessionDate": session_date,
                "Alias": alias,
                "Hand": g["Hand"].iloc[0] if "Hand" in g.columns and len(g) else "",
                "TotalShots": int(len(g)),
                "ClubsPlayed": int(clubs_played) if not pd.isna(clubs_played) else "",
                "Driver_Fairway_pm20m_Count": fair_cnt,
                "Driver_fairway_+-20_count": fair_cnt,
                "Driver_Shots_Carry_gt120m": drv_cnt_gt120,
                "Driver_AvgCarry_gt120m": ("" if math.isnan(drv_avg_carry_gt120) else round(drv_avg_carry_gt120, 1)),
            })

    sessions_df = pd.DataFrame(sessions_rows)

    # Write Base Excel
    base_xlsx = work / "Base_Coaching_Golf.xlsx"
    with pd.ExcelWriter(base_xlsx, engine="openpyxl") as writer:
        shots.to_excel(writer, sheet_name="Shots", index=False)
        sessions_df.to_excel(writer, sheet_name="Sessions", index=False)

    # Create PDFs (valid) - simple placeholders with stats
    ddmmyyyy = session_date.replace("-", "")
    student_pdfs: Dict[str, List[str]] = {}
    group_pdfs: List[str] = []

    if not shots.empty:
        for alias, g in shots.groupby("Alias"):
            student_pdfs[alias] = []
            # quick stats
            drv = g[g["IsDriver"] == True]
            drv_good = drv[drv["Carry"] > 120] if "Carry" in drv.columns else drv
            avg_carry = float(drv_good["Carry"].mean()) if "Carry" in drv_good.columns and len(drv_good) else float("nan")
            avg_off = float(drv["Offline"].mean()) if "Offline" in drv.columns and len(drv) else float("nan")
            lines = [
                f"Session: {session_date}",
                f"Alias: {alias}",
                f"Hand: {g['Hand'].iloc[0] if 'Hand' in g.columns and len(g) else ''}",
                f"Total shots: {len(g)}",
                f"Driver shots: {len(drv)}",
                f"Driver shots (carry>120m): {len(drv_good)}",
                f"Driver avg carry (m): {avg_carry:.1f}" if not math.isnan(avg_carry) else "Driver avg carry (m): n/a",
                f"Driver avg offline (m): {avg_off:.1f}" if not math.isnan(avg_off) else "Driver avg offline (m): n/a",
            ]
            for letter in ["A","B","C","D","E","F","G","H"]:
                p = work / f"Model{letter}_{alias}_{ddmmyyyy}.pdf"
                if letter == "A":
                    # Model A (GOLD) with graphs (driver-focused)
                    try:
                        build_modelA_gold(shots, alias=alias, hand=(g["Hand"].iloc[0] if "Hand" in g.columns and len(g) else "R"),
                                          session_date=session_date, out_pdf=str(p))
                    except Exception as e:
                        # fallback to simple pdf with the error
                        _simple_pdf(str(p), f"Model A — {alias}", lines + [f"ERREUR ModelA: {e}"])
                elif letter == "B":
                    # Model B (GOLD) driver-only
                    try:
                        build_modelB_gold(shots, alias=alias, hand=(g["Hand"].iloc[0] if "Hand" in g.columns and len(g) else "R"),
                                          session_date=session_date, out_pdf=str(p))
                    except Exception as e:
                        _simple_pdf(str(p), f"Model B — {alias}", lines + [f"ERREUR ModelB: {e}"])
                else:
                    _simple_pdf(str(p), f"Model {letter} — {alias}", lines)
                student_pdfs[alias].append(str(p))

# Group docs
        g_lines = [f"Session: {session_date}", f"Players: {', '.join(sorted(student_pdfs.keys()))}"]

        # Model C (GOLD) — comparatif joueurs (driver-only)
        pC = work / f"ModelC_GROUPE_{ddmmyyyy}.pdf"
        try:
            build_modelC_gold(shots, roster=roster, session_date=session_date, out_pdf=str(pC))
        except Exception as e:
            _simple_pdf(str(pC), "Model C — GROUPE", g_lines + [f"ERREUR ModelC: {e}"])
        group_pdfs.append(str(pC))

        # Model D (GOLD) — synthèse coach groupe (driver-only)
        pD = work / f"ModelD_GROUPE_{ddmmyyyy}.pdf"
        try:
            build_modelD_gold(shots, roster=roster, session_date=session_date, out_pdf=str(pD))
        except Exception as e:
            _simple_pdf(str(pD), "Model D — GROUPE", g_lines + [f"ERREUR ModelD: {e}"])
        group_pdfs.append(str(pD))

        # Other group placeholders
        for letter in ["F","G","H"]:
            p = work / f"Model{letter}_GROUPE_{ddmmyyyy}.pdf"
            _simple_pdf(str(p), f"Model {letter} — GROUPE", g_lines)
            group_pdfs.append(str(p))

    return {"base_xlsx": str(base_xlsx), "student_pdfs": student_pdfs, "group_pdfs": group_pdfs}
