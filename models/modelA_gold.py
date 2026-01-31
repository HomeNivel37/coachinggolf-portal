
from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# --- Ellipse helper ---
def _ellipse_params(x: np.ndarray, y: np.ndarray, level: float) -> tuple[float,float,float,float,float] | None:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if len(x) < 5:
        return None
    cov = np.cov(np.vstack([x, y]))
    vals, vecs = np.linalg.eigh(cov)
    order = vals.argsort()[::-1]
    vals = vals[order]
    vecs = vecs[:, order]
    # chi-square quantile for 2 DOF: 68% and 95%
    chi2 = 2.27886856637673 if abs(level-0.68) < 0.02 else 5.991464547107979
    a = math.sqrt(max(vals[0], 0) * chi2)
    b = math.sqrt(max(vals[1], 0) * chi2)
    angle = math.degrees(math.atan2(vecs[1,0], vecs[0,0]))
    cx, cy = float(np.mean(x)), float(np.mean(y))
    return cx, cy, 2*a, 2*b, angle

def _save_fig(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)

def build_modelA_gold(shots: pd.DataFrame, alias: str, hand: str, session_date: str, out_pdf: str) -> str:
    df = shots[shots["Alias"] == alias].copy()
    # Driver only; exclude carry < 120 m
    drv = df[(df.get("IsDriver", False) == True)].copy()
    if "Carry" in drv.columns:
        drv = drv[pd.to_numeric(drv["Carry"], errors="coerce") > 120].copy()

    # numeric
    for c in ["Carry", "Offline", "Smash", "HLA", "VLA", "SpinLat", "BackSpin", "SpinAxis"]:
        if c in drv.columns:
            drv[c] = pd.to_numeric(drv[c], errors="coerce")

    styles = getSampleStyleSheet()
    story = []
    doc = SimpleDocTemplate(out_pdf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)

    # Cover
    story.append(Paragraph("<b>MODEL A (GOLD)</b>", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Date de la session :</b> {session_date}", styles["Normal"]))
    story.append(Paragraph(f"<b>Nom du joueur :</b> {alias}", styles["Normal"]))
    story.append(Paragraph(f"<b>Dextérité :</b> {'gaucher' if str(hand).upper().startswith('L') else 'droitier'}", styles["Normal"]))
    story.append(Paragraph(f"<b>Nombre total de coups :</b> {len(df)}", styles["Normal"]))
    club_col = "Club Name" if "Club Name" in df.columns else ("Club" if "Club" in df.columns else None)
    nclubs = int(df[club_col].nunique()) if club_col else 0
    story.append(Paragraph(f"<b>Nombre de clubs joués :</b> {nclubs}", styles["Normal"]))
    story.append(PageBreak())

    # Figure paths
    outp = Path(out_pdf).parent
    p1 = outp / f"{alias}_A_driver_carry_offline.png"
    p2 = outp / f"{alias}_A_smash_carry.png"
    p3 = outp / f"{alias}_A_hla_carry.png"
    p4 = outp / f"{alias}_A_vla_carry.png"
    p5 = outp / f"{alias}_A_spinlat_carry.png"

    # A. Carry vs Offline
    story.append(Paragraph("1) DRIVER", styles["Heading1"]))
    story.append(Paragraph("A. Carry vs Offline", styles["Heading2"]))
    if len(drv) >= 1 and {"Carry","Offline"}.issubset(drv.columns):
        x = drv["Carry"].to_numpy()
        y = drv["Offline"].to_numpy()
        smash = drv["Smash"].to_numpy() if "Smash" in drv.columns else None

        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        ax.axhspan(-20, 20, alpha=0.15)  # fairway band
        ax.axhline(0, linewidth=1)
        ax.axvline(0, linewidth=1)
        ax.set_ylim(-50, 50)
        if smash is not None and np.isfinite(smash).any():
            sc = ax.scatter(x, y, c=smash, s=28)
            cb = plt.colorbar(sc, ax=ax)
            cb.set_label("Smash")
        else:
            ax.scatter(x, y, s=28)

        # Ellipses
        from matplotlib.patches import Ellipse as MplEllipse
        e68 = _ellipse_params(x, y, 0.68)
        e95 = _ellipse_params(x, y, 0.95)
        for e, ls in [(e68, "-"), (e95, "--")]:
            if e:
                cx, cy, w, h, ang = e
                ax.add_patch(MplEllipse((cx, cy), w, h, angle=ang, fill=False, linestyle=ls, linewidth=2))
        ax.set_xlabel("Carry (m)")
        ax.set_ylabel("Offline (m)")
        ax.set_title("Driver — Carry vs Offline")
        _save_fig(fig, p1)

        story.append(Image(str(p1), width=7.2*inch, height=4.2*inch))
        story.append(Spacer(1, 8))

        # Coach comment
        n = int(len(drv))
        pct_fw = float(np.nanmean((np.abs(y) <= 20).astype(float)) * 100.0) if n else 0.0
        avg_c = float(np.nanmean(x)) if n else float("nan")
        std_off = float(np.nanstd(y)) if n else float("nan")
        avg_sm = float(np.nanmean(smash)) if smash is not None and np.isfinite(smash).any() else float("nan")
        comment = f"Sur {n} drives (carry > 120 m), carry moyen {avg_c:.1f} m, dispersion offline (écart-type) {std_off:.1f} m, {pct_fw:.0f}% dans la zone ±20 m."
        if not math.isnan(avg_sm):
            comment += f" Smash moyen {avg_sm:.2f}."
        story.append(Paragraph(comment, styles["BodyText"]))
    else:
        story.append(Paragraph("Aucun drive exploitable (carry > 120 m). Vérifier les données.", styles["BodyText"]))
    story.append(PageBreak())

    # B. Smash vs Carry
    story.append(Paragraph("B. Efficacité d'impact — Smash vs Carry", styles["Heading2"]))
    if len(drv) >= 1 and {"Carry","Smash"}.issubset(drv.columns):
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.scatter(drv["Smash"], drv["Carry"], s=28)
        ax.set_xlabel("Smash factor")
        ax.set_ylabel("Carry (m)")
        ax.set_title("Driver — Smash vs Carry")
        _save_fig(fig, p2)
        story.append(Image(str(p2), width=7.2*inch, height=3.6*inch))
        story.append(Spacer(1, 6))
        story.append(Paragraph("Lecture coach : viser une zone stable de smash élevé sur la majorité des coups. Un smash instable traduit un contact irrégulier (centrage/face).", styles["BodyText"]))
    else:
        story.append(Paragraph("Smash ou Carry manquant : impossible de tracer ce graphe.", styles["BodyText"]))
    story.append(PageBreak())

    # C. Angles
    story.append(Paragraph("C. Angles de lancement — HLA & VLA", styles["Heading2"]))
    if len(drv) >= 1 and {"HLA","Carry"}.issubset(drv.columns):
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.scatter(drv["HLA"], drv["Carry"], s=28)
        ax.axvline(0, linewidth=1)
        ax.set_xlabel("HLA (deg)")
        ax.set_ylabel("Carry (m)")
        ax.set_title("Driver — HLA vs Carry")
        _save_fig(fig, p3)
        story.append(Image(str(p3), width=7.2*inch, height=3.6*inch))
        story.append(Spacer(1, 8))
    if len(drv) >= 1 and {"VLA","Carry"}.issubset(drv.columns):
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.scatter(drv["VLA"], drv["Carry"], s=28)
        ax.axvline(0, linewidth=1)
        ax.set_xlabel("VLA (deg)")
        ax.set_ylabel("Carry (m)")
        ax.set_title("Driver — VLA vs Carry")
        _save_fig(fig, p4)
        story.append(Image(str(p4), width=7.2*inch, height=3.6*inch))
        story.append(Spacer(1, 6))
    story.append(Paragraph("Lecture coach : HLA proche de 0 améliore la dispersion; VLA cohérent aide à stabiliser la hauteur et l'efficacité.", styles["BodyText"]))
    story.append(PageBreak())

    # D. Spin latéral
    story.append(Paragraph("D. Spin latéral — contrôle de trajectoire", styles["Heading2"]))
    if len(drv) >= 1 and {"Carry","SpinLat"}.issubset(drv.columns):
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        ax.scatter(drv["Carry"], drv["SpinLat"], s=28)
        ax.axhline(0, linewidth=1)
        ax.set_xlabel("Carry (m)")
        ax.set_ylabel("Spin latéral (rpm)")
        ax.set_title("Driver — Spin latéral vs Carry")
        _save_fig(fig, p5)
        story.append(Image(str(p5), width=7.2*inch, height=3.6*inch))
        story.append(Spacer(1, 6))
        story.append(Paragraph("Lecture coach : un spin latéral élevé augmente la courbure et réduit la marge. Chercher une fenêtre de spin latéral resserrée.", styles["BodyText"]))
    else:
        story.append(Paragraph("SpinLat ou Carry manquant : impossible de tracer ce graphe.", styles["BodyText"]))

    doc.build(story)
    return out_pdf
