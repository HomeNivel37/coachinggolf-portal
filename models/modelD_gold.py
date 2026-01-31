
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

from core.metrics import to_signed_lr

def _num(s):
    return pd.to_numeric(s, errors="coerce")

def _driver_df(shots: pd.DataFrame) -> pd.DataFrame:
    df = shots.copy()
    if "IsDriver" in df.columns:
        df = df[df["IsDriver"] == True]
    carry_col = "Carry" if "Carry" in df.columns else "Carry Dist (m)"
    df[carry_col] = _num(df[carry_col])
    df = df[df[carry_col] > 120].copy()
    return df

def _kpis(drv: pd.DataFrame) -> pd.DataFrame:
    carry_col = "Carry" if "Carry" in drv.columns else "Carry Dist (m)"
    off_col = "Offline" if "Offline" in drv.columns else "Offline (m)"
    tmp = drv.copy()
    tmp["Carry_m"] = _num(tmp[carry_col])
    tmp["Offline_m"] = tmp[off_col].apply(to_signed_lr) if tmp[off_col].dtype == object else _num(tmp[off_col])
    tmp["AbsOff"] = tmp["Offline_m"].abs()
    tmp["Smash"] = _num(tmp.get("Smash", np.nan))
    g = tmp.groupby("Alias", dropna=False)
    out = pd.DataFrame({
        "Alias": g.size().index,
        "N": g.size().values,
        "Carry": g["Carry_m"].mean().values,
        "AbsOff": g["AbsOff"].mean().values,
        "Fairway±20%": g["Offline_m"].apply(lambda s: float(np.nanmean((np.abs(s)<=20).astype(float))*100.0)).values,
        "Smash": g["Smash"].mean().values,
    })
    return out

def _plot_rank(df: pd.DataFrame, col: str, title: str, out_png: Path):
    s = df.sort_values(col, ascending=False if col in ("Carry","Smash","Fairway±20%") else True)
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    ax.bar(s["Alias"].astype(str), s[col].astype(float))
    ax.set_title(title)
    ax.set_ylabel(col)
    fig.tight_layout()
    fig.savefig(out_png, dpi=200)
    plt.close(fig)

def build_modelD_gold(shots_df: pd.DataFrame, roster: dict, session_date: str, out_pdf: str) -> str:
    out_path = Path(out_pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    drv = _driver_df(shots_df)
    k = _kpis(drv)

    img1 = out_path.with_suffix(".carry.png")
    img2 = out_path.with_suffix(".acc.png")
    img3 = out_path.with_suffix(".smash.png")

    _plot_rank(k, "Carry", "Groupe — Carry moyen (driver>120m)", img1)
    _plot_rank(k, "Fairway±20%", "Groupe — % fairway (±20m) (driver>120m)", img2)
    _plot_rank(k, "Smash", "Groupe — Smash moyen (driver>120m)", img3)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out_path))
    story = []
    story.append(Paragraph("<b>MODEL D (GOLD) — Synthèse coach groupe</b>", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Date de session :</b> {session_date}", styles["Normal"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("1) KPI groupe (driver>120m)", styles["Heading1"]))
    show = k.copy()
    def f1(x): return "" if pd.isna(x) else f"{x:.1f}"
    def f0(x): return "" if pd.isna(x) else f"{x:.0f}"
    def f2(x): return "" if pd.isna(x) else f"{x:.2f}"
    show["Carry"] = show["Carry"].map(f1)
    show["AbsOff"] = show["AbsOff"].map(f1)
    show["Fairway±20%"] = show["Fairway±20%"].map(f0)
    show["Smash"] = show["Smash"].map(f2)

    data = [list(show.columns)] + show.values.tolist()
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f2f2f2")),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#dddddd")),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("2) Lecture rapide (classements)", styles["Heading1"]))
    story.append(Image(str(img1), width=7.2*inch, height=3.2*inch))
    story.append(Spacer(1, 8))
    story.append(Image(str(img2), width=7.2*inch, height=3.2*inch))
    story.append(Spacer(1, 8))
    story.append(Image(str(img3), width=7.2*inch, height=3.2*inch))
    story.append(Spacer(1, 10))

    # Coach conclusions
    if not k.empty:
        best_carry = k.loc[k["Carry"].astype(float).idxmax()]
        best_acc = k.loc[k["Fairway±20%"].astype(float).idxmax()]
        best_smash = k.loc[k["Smash"].astype(float).idxmax()] if k["Smash"].notna().any() else None
        lines = []
        lines.append(f"• Leader distance : {best_carry['Alias']} (carry {float(best_carry['Carry']):.1f} m).")
        lines.append(f"• Leader précision : {best_acc['Alias']} ({float(best_acc['Fairway±20%']):.0f}% dans ±20 m).")
        if best_smash is not None:
            lines.append(f"• Leader efficacité : {best_smash['Alias']} (smash {float(best_smash['Smash']):.2f}).")
        lines.append("Axes groupe (2 mois) : (1) contact centré + vitesse contrôlée (smash), (2) start line (HLA) + face/path, (3) routine de dispersion (cible/alignement).")
        story.append(Paragraph("3) Analyse coach & plan groupe", styles["Heading1"]))
        story.append(Paragraph("<br/>".join(lines), styles["BodyText"]))

    doc.build(story)
    return str(out_path)
