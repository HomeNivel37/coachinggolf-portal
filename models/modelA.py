
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from core.metrics import ellipse_from_cov, ellipse_indicative
from pdf.theme import PAGE_SIZE, MARGIN, TABLE_HEADER_BG, TABLE_GRID


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _is_long_club(club: str) -> bool:
    c = str(club).upper().strip()
    if c in ("DR", "DRIVER", "1W", "W1"):
        return True
    if c.startswith("H") or c.startswith("W"):
        return True
    for p in ("F", "I"):
        if c.startswith(p):
            try:
                n = int(c[1:])
                return 3 <= n <= 7
            except Exception:
                pass
    return False


def _save(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _plot_driver_disp(drv: pd.DataFrame, out_png: Path):
    carry = _num(drv["Carry"])
    off = _num(drv["Offline"])
    smash = _num(drv.get("Smash", np.nan))

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.axhspan(-20, 20, alpha=0.15)
    ax.axhline(0, linewidth=1)
    ax.axvline(0, linewidth=1)
    sc = ax.scatter(carry, off, c=smash, s=28)
    cb = plt.colorbar(sc, ax=ax)
    cb.set_label("Smash")

    e68 = ellipse_from_cov(carry.values, off.values, 0.68)
    e95 = ellipse_from_cov(carry.values, off.values, 0.95)
    for e, ls in [(e68, "-"), (e95, "--")]:
        if e:
            from matplotlib.patches import Ellipse as MplEllipse
            ax.add_patch(MplEllipse((e.cx, e.cy), e.width, e.height, angle=e.angle_deg,
                                    fill=False, linestyle=ls, linewidth=2))

    ax.set_xlabel("Carry (m)")
    ax.set_ylabel("Offline (m)")
    ax.set_ylim(-50, 50)
    ax.set_title("Driver — Carry vs Offline")
    _save(fig, out_png)

    stats = {
        "n": int(len(drv)),
        "avg_carry": float(np.nanmean(carry)),
        "avg_smash": float(np.nanmean(smash)),
        "pct_fairway": float(np.nanmean((off.abs() <= 20).astype(float)) * 100.0) if len(drv) else 0.0,
        "std_off": float(np.nanstd(off)),
    }
    return stats


def _plot_scatter(x, y, xlabel, ylabel, title, out_png: Path, hline0=False):
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.scatter(x, y, s=28)
    if hline0:
        ax.axhline(0, linewidth=1)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    _save(fig, out_png)


def _recompute_spins(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    back = _num(out.get("BackSpin", np.nan))
    axis = _num(out.get("SpinAxis", np.nan))
    axis_rad = np.deg2rad(axis)
    cosv = np.cos(axis_rad).replace(0, np.nan)
    spin_total = back / cosv
    spin_lat = spin_total * np.sin(axis_rad)
    out["SpinTotal"] = spin_total
    out["SpinLat"] = spin_lat
    out["BackSpin"] = back
    out["SpinAxis"] = axis
    return out


def _coach_driver_comment(stats):
    n = stats["n"]
    if n == 0:
        return "Aucun drive > 120 m détecté : vérifie le filtre ou les données Carry."
    return (
        f"Sur {n} drives (carry > 120 m), carry moyen {stats['avg_carry']:.1f} m, "
        f"smash moyen {stats['avg_smash']:.2f}. "
        f"Dispersion offline (écart-type) {stats['std_off']:.1f} m, "
        f"{stats['pct_fairway']:.0f}% dans la zone ±20 m."
    )


def build_modelA_gold(shots_df: pd.DataFrame, sessions_df: pd.DataFrame | None,
                      alias: str, handedness: str, session_date: str, out_pdf: str) -> str:
    df = shots_df.copy()
    df = df[df["Alias"] == alias].copy()
    if df.empty:
        raise ValueError(f"No shots for alias={alias}")

    # Ensure Club column
    if "Club" not in df.columns:
        df["Club"] = df.get("Club Name", "UNKNOWN").astype(str)

    df = _recompute_spins(df)

    # Driver (carry>120)
    drv = df[df.get("IsDriver", False) == True].copy()
    drv = drv[_num(drv["Carry"]) > 120].copy()
    drv = _recompute_spins(drv)

    out_path = Path(out_pdf)
    workdir = out_path.parent
    workdir.mkdir(parents=True, exist_ok=True)

    fig1 = workdir / f"modelA_{alias}_driver_disp.png"
    fig2 = workdir / f"modelA_{alias}_smash_carry.png"
    fig3 = workdir / f"modelA_{alias}_hla_carry.png"
    fig4 = workdir / f"modelA_{alias}_vla_carry.png"
    fig5 = workdir / f"modelA_{alias}_spinlat.png"
    fig6 = workdir / f"modelA_{alias}_long_spin.png"
    fig7 = workdir / f"modelA_{alias}_allclubs.png"

    stats = _plot_driver_disp(drv, fig1)
    _plot_scatter(_num(drv.get("Smash", np.nan)), _num(drv["Carry"]),
                  "Smash factor", "Carry (m)", "Driver — Smash vs Carry", fig2)
    _plot_scatter(_num(drv.get("HLA", np.nan)), _num(drv["Carry"]),
                  "HLA (deg)", "Carry (m)", "Driver — HLA vs Carry", fig3)
    _plot_scatter(_num(drv.get("VLA", np.nan)), _num(drv["Carry"]),
                  "VLA (deg)", "Carry (m)", "Driver — VLA vs Carry", fig4)
    _plot_scatter(_num(drv["Carry"]), _num(drv.get("SpinLat", np.nan)),
                  "Carry (m)", "Spin latéral (rpm)", "Driver — Spin latéral", fig5, hline0=True)

    # Long clubs spin mean vs carry mean
    long_df = df[df["Club"].apply(_is_long_club)].copy()
    grp = long_df.groupby("Club").agg(
        AvgCarry=("Carry","mean"),
        AvgBack=("BackSpin","mean"),
        AvgLat=("SpinLat","mean"),
        Shots=("Carry","count")
    ).reset_index()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.scatter(grp["AvgCarry"], grp["AvgBack"], marker="o", s=60)
    ax.scatter(grp["AvgCarry"], grp["AvgLat"], marker="^", s=60)
    for _, r in grp.iterrows():
        ax.annotate(str(r["Club"]), (r["AvgCarry"], r["AvgBack"]), fontsize=8)
    ax.set_xlabel("Carry moyen (m)")
    ax.set_ylabel("Spin (rpm)")
    ax.set_title("Clubs longs — Spin moyen vs Carry moyen")
    _save(fig, fig6)

    # All clubs dispersion + ellipse 95% per club
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.axhline(0, linewidth=1)
    ax.axvline(0, linewidth=1)
    clubs = sorted(df["Club"].dropna().unique().tolist())
    cmap = plt.get_cmap("tab20")
    for i, club in enumerate(clubs):
        sub = df[df["Club"] == club]
        x = _num(sub["Carry"])
        y = _num(sub["Offline"])
        ax.scatter(x, y, s=18, label=str(club), color=cmap(i % 20))
        if len(sub) >= 5:
            e = ellipse_from_cov(x.values, y.values, 0.95)
            if e:
                from matplotlib.patches import Ellipse as MplEllipse
                ax.add_patch(MplEllipse((e.cx, e.cy), e.width, e.height, angle=e.angle_deg,
                                        fill=False, linewidth=1.6, color=cmap(i % 20)))
        else:
            e = ellipse_indicative(x.values, y.values)
            if e:
                from matplotlib.patches import Ellipse as MplEllipse
                ax.add_patch(MplEllipse((e.cx, e.cy), e.width, e.height, angle=e.angle_deg,
                                        fill=False, linewidth=1.2, linestyle="--", color=cmap(i % 20)))
    ax.set_xlabel("Carry (m)")
    ax.set_ylabel("Offline (m)")
    ax.set_title("Tous les clubs — Carry vs Offline")
    ax.legend(fontsize=7, ncol=2, frameon=False)
    _save(fig, fig7)

    # Summary table
    summary = (
        df.groupby("Club")
        .agg(
            Shots=("Carry","count"),
            AvgCarry=("Carry","mean"),
            StdCarry=("Carry","std"),
            AvgOffline=("Offline","mean"),
            StdOffline=("Offline","std"),
            AvgSmash=("Smash","mean"),
            AvgBackSpin=("BackSpin","mean"),
            AvgLatSpin=("SpinLat","mean"),
        )
        .reset_index()
        .sort_values("AvgCarry", ascending=False)
    )

    styles = getSampleStyleSheet()
    story = []

    # Cover
    story.append(Paragraph("<b>MODEL A (GOLD)</b>", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Date de la session :</b> {session_date}", styles["Normal"]))
    story.append(Paragraph(f"<b>Nom / alias :</b> {alias}", styles["Normal"]))
    story.append(Paragraph(f"<b>Dextérité :</b> {'gaucher' if str(handedness).upper().startswith('L') else 'droitier'}", styles["Normal"]))
    story.append(Paragraph(f"<b>Nombre total de coups :</b> {int(df.shape[0])}", styles["Normal"]))
    story.append(Paragraph(f"<b>Nombre de clubs joués :</b> {df['Club'].nunique()}", styles["Normal"]))
    story.append(PageBreak())

    # Driver pages
    story.append(Paragraph("1) DRIVER", styles["Heading1"]))
    story.append(Paragraph("A. Carry vs Offline", styles["Heading2"]))
    story.append(Image(str(fig1), width=7.2*inch, height=4.2*inch))
    story.append(Spacer(1, 6))
    story.append(Paragraph(_coach_driver_comment(stats), styles["BodyText"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("B. Smash factor vs Carry", styles["Heading2"]))
    story.append(Image(str(fig2), width=7.2*inch, height=3.6*inch))
    story.append(PageBreak())

    story.append(Paragraph("C. Angles de lancement", styles["Heading2"]))
    story.append(Image(str(fig3), width=7.2*inch, height=3.6*inch))
    story.append(Spacer(1, 8))
    story.append(Image(str(fig4), width=7.2*inch, height=3.6*inch))
    story.append(PageBreak())

    story.append(Paragraph("D. Spin latéral", styles["Heading2"]))
    story.append(Image(str(fig5), width=7.2*inch, height=3.6*inch))
    story.append(PageBreak())

    # Long clubs
    story.append(Paragraph("2) CLUBS LONGS", styles["Heading1"]))
    story.append(Image(str(fig6), width=7.2*inch, height=4.2*inch))
    story.append(PageBreak())

    # All clubs + table
    story.append(Paragraph("3) TOUS LES CLUBS", styles["Heading1"]))
    story.append(Image(str(fig7), width=7.2*inch, height=4.2*inch))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Tableau de synthèse chiffrée", styles["Heading2"]))
    cols = ["Club","Shots","AvgCarry","StdCarry","AvgOffline","StdOffline","AvgSmash","AvgBackSpin","AvgLatSpin"]
    tbl = summary[cols].copy()
    for c in cols[2:]:
        tbl[c] = tbl[c].map(lambda v: "" if pd.isna(v) else f"{v:.1f}")
    data = [cols] + tbl.values.tolist()
    t = Table(data, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), TABLE_HEADER_BG),
        ("GRID", (0,0), (-1,-1), 0.5, TABLE_GRID),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(PageBreak())

    story.append(Paragraph("4) PLAN D’ENTRAÎNEMENT (objectif 2 mois)", styles["Heading1"]))
    story.append(Paragraph("Objectif : stabiliser la dispersion driver et améliorer la régularité d’impact.", styles["BodyText"]))
    story.append(Paragraph("Axes : centrage/contact, contrôle du point de départ (HLA), routine/tempo.", styles["BodyText"]))
    story.append(Paragraph("Progrès attendus : +% fairways ±20m, ellipse 68% plus serrée, carry stable.", styles["BodyText"]))

    doc = SimpleDocTemplate(str(out_path), pagesize=PAGE_SIZE,
                            leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN)
    doc.build(story)
    return str(out_path)
