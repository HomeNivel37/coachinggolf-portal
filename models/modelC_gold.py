
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

from core.metrics import ellipse_from_cov, to_signed_lr

def _num(s):
    return pd.to_numeric(s, errors="coerce")

def _driver_df(shots: pd.DataFrame) -> pd.DataFrame:
    df = shots.copy()
    # Accept either IsDriver boolean or ClubName
    if "IsDriver" in df.columns:
        df = df[df["IsDriver"] == True]
    elif "Club Name" in df.columns:
        df = df[df["Club Name"].astype(str).str.upper().str.contains("DR")]
    # Driver filter carry > 120m (as in ModelA)
    carry_col = "Carry" if "Carry" in df.columns else "Carry Dist (m)"
    df[carry_col] = _num(df[carry_col])
    df = df[df[carry_col] > 120].copy()
    return df

def _compute_spin_lat(df: pd.DataFrame) -> pd.Series:
    back = _num(df.get("BackSpin", df.get("Back Spin", np.nan)))
    axis = _num(df.get("SpinAxis", df.get("Spin Axis", np.nan)))
    axis_rad = np.deg2rad(axis)
    cosv = np.cos(axis_rad)
    cosv = cosv.where(np.abs(cosv) > 1e-9, np.nan)
    spin_total = back / cosv
    spin_lat = spin_total * np.sin(axis_rad)
    return spin_lat

def _summary_table(drv: pd.DataFrame, roster: dict) -> pd.DataFrame:
    carry_col = "Carry" if "Carry" in drv.columns else "Carry Dist (m)"
    off_col = "Offline" if "Offline" in drv.columns else "Offline (m)"
    if off_col not in drv.columns and "Offline (m)" in drv.columns:
        off_col = "Offline (m)"
    tmp = drv.copy()
    # Ensure offline numeric if still LR text
    tmp[off_col] = tmp[off_col].apply(to_signed_lr) if tmp[off_col].dtype == object else _num(tmp[off_col])
    tmp["Carry_m"] = _num(tmp[carry_col])
    tmp["Smash"] = _num(tmp.get("Smash", np.nan))
    tmp["BackSpin"] = _num(tmp.get("BackSpin", tmp.get("Back Spin", np.nan)))
    tmp["SpinAxis"] = _num(tmp.get("SpinAxis", tmp.get("Spin Axis", np.nan)))
    tmp["SpinLat"] = _compute_spin_lat(tmp)
    tmp["HLA"] = tmp.get("HLA", np.nan)
    tmp["VLA"] = tmp.get("VLA", np.nan)
    tmp["PeakHeight"] = _num(tmp.get("PeakHeight", tmp.get("Peak Height (m)", np.nan)))
    g = tmp.groupby("Alias", dropna=False)
    out = pd.DataFrame({
        "Alias": g.size().index,
        "N": g.size().values,
        "AvgCarry": g["Carry_m"].mean().values,
        "StdCarry": g["Carry_m"].std(ddof=0).values,
        "AvgOffline": g[off_col].mean().values,
        "StdOffline": g[off_col].std(ddof=0).values,
        "AvgAbsOffline": g[off_col].apply(lambda s: np.nanmean(np.abs(s))).values,
        "Fairway±20%": g[off_col].apply(lambda s: float(np.nanmean((np.abs(s) <= 20).astype(float))*100.0)).values,
        "AvgSmash": g["Smash"].mean().values,
        "AvgBackSpin": g["BackSpin"].mean().values,
        "AvgSpinAxis": g["SpinAxis"].mean().values,
        "AvgSpinLat": g["SpinLat"].mean().values,
        "AvgHLA": g["HLA"].apply(_num).mean().values,
        "AvgVLA": g["VLA"].apply(_num).mean().values,
        "AvgPeakH": g["PeakHeight"].mean().values,
    })
    return out

def _plot_dispersion(drv: pd.DataFrame, out_png: Path, roster: dict):
    carry_col = "Carry" if "Carry" in drv.columns else "Carry Dist (m)"
    off_col = "Offline" if "Offline" in drv.columns else "Offline (m)"
    df = drv.copy()
    df["Carry_m"] = _num(df[carry_col])
    df["Offline_m"] = df[off_col].apply(to_signed_lr) if df[off_col].dtype == object else _num(df[off_col])

    fig, ax = plt.subplots(figsize=(7.2,4.2))
    ax.axhspan(-20, 20, alpha=0.12)
    ax.axhline(0, linewidth=1)
    ax.axvline(0, linewidth=1)

    aliases = sorted(df["Alias"].dropna().unique())
    for alias in aliases:
        s = df[df["Alias"]==alias].dropna(subset=["Carry_m","Offline_m"])
        x = s["Carry_m"].to_numpy()
        y = s["Offline_m"].to_numpy()
        ax.scatter(x, y, s=28, label=alias)
        e95 = ellipse_from_cov(x, y, 0.95)
        if e95:
            from matplotlib.patches import Ellipse as MplEllipse
            ax.add_patch(MplEllipse((e95.cx,e95.cy), e95.width, e95.height, angle=e95.angle_deg,
                                    fill=False, linestyle="--", linewidth=2))

    ax.set_xlabel("Carry (m) — driver (carry>120m)")
    ax.set_ylabel("Offline (m)")
    ax.set_ylim(-50, 50)
    ax.set_title("Comparatif driver — Carry vs Offline (ellipse 95%)")
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

def _coach_takeaways(summary: pd.DataFrame) -> str:
    if summary.empty:
        return "Données insuffisantes pour comparer les joueurs (driver)."
    # Identify best carry, best accuracy, best smash
    best_carry = summary.loc[summary["AvgCarry"].idxmax()]
    best_acc = summary.loc[summary["AvgAbsOffline"].idxmin()]
    best_smash = summary.loc[summary["AvgSmash"].idxmax()] if summary["AvgSmash"].notna().any() else None

    lines = []
    lines.append(f"• Distance (carry driver>120m) : meilleur carry = {best_carry['Alias']} ({best_carry['AvgCarry']:.1f} m).")
    lines.append(f"• Précision : meilleure dispersion latérale (|offline| moyen) = {best_acc['Alias']} ({best_acc['AvgAbsOffline']:.1f} m), fairway ±20 m = {best_acc['Fairway±20%']:.0f}%.")
    if best_smash is not None and pd.notna(best_smash["AvgSmash"]):
        lines.append(f"• Efficacité d'impact : meilleur smash moyen = {best_smash['Alias']} ({best_smash['AvgSmash']:.2f}).")
    lines.append("Recommandation : prioriser (1) la régularité (|offline| + fairway%), puis (2) le smash, puis (3) l’optimisation spin/angles.")
    return "<br/>".join(lines)

def build_modelC_gold(shots_df: pd.DataFrame, roster: dict, session_date: str, out_pdf: str) -> str:
    out_path = Path(out_pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    drv = _driver_df(shots_df)
    summary = _summary_table(drv, roster)

    img1 = out_path.with_suffix(".disp.png")
    _plot_dispersion(drv, img1, roster)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out_path))
    story = []
    story.append(Paragraph("<b>MODEL C (GOLD) — Comparatif 3 joueurs</b>", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Date de session :</b> {session_date}", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("1) Driver — KPI comparatifs (carry>120m)", styles["Heading1"]))

    # Table
    table_df = summary.copy()
    # format
    def f1(x): return "" if pd.isna(x) else f"{x:.1f}"
    def f0(x): return "" if pd.isna(x) else f"{x:.0f}"
    def f2(x): return "" if pd.isna(x) else f"{x:.2f}"
    show = table_df[["Alias","N","AvgCarry","StdCarry","AvgOffline","StdOffline","AvgAbsOffline","Fairway±20%","AvgSmash","AvgBackSpin","AvgSpinAxis","AvgSpinLat","AvgHLA","AvgVLA","AvgPeakH"]].copy()
    for c in ["AvgCarry","StdCarry","AvgOffline","StdOffline","AvgAbsOffline","AvgSpinAxis","AvgHLA","AvgVLA","AvgPeakH"]:
        show[c] = show[c].map(f1)
    for c in ["AvgBackSpin","AvgSpinLat"]:
        show[c] = show[c].map(f0)
    show["Fairway±20%"] = show["Fairway±20%"].map(f0)
    show["AvgSmash"] = show["AvgSmash"].map(f2)

    data = [list(show.columns)] + show.values.tolist()
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2f2f2")),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Image(str(img1), width=7.2*inch, height=4.2*inch))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Analyse coach :", styles["Heading2"]))
    story.append(Paragraph(_coach_takeaways(summary), styles["BodyText"]))

    doc.build(story)
    return str(out_path)
