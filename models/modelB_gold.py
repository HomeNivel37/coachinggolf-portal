
from __future__ import annotations

from pathlib import Path
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

# Reuse helpers from ModelA if present
try:
    from core.metrics import ellipse_from_cov
except Exception:
    ellipse_from_cov = None


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _safe_mean(x):
    x = pd.to_numeric(x, errors="coerce")
    x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else float("nan")


def _safe_std(x):
    x = pd.to_numeric(x, errors="coerce")
    x = x[np.isfinite(x)]
    return float(x.std(ddof=0)) if len(x) else float("nan")


def _save(fig, path: Path):
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def _hand_label(hand: str) -> str:
    return "gaucher" if str(hand).upper().startswith("L") else "droitier"


def _curve_label(hand: str, spin_axis: float) -> str:
    """
    Convention after decoding:
      negative => 'L', positive => 'R'
    For right-handed: curve left = draw, curve right = fade.
    For left-handed : curve left = fade, curve right = draw.
    """
    if not np.isfinite(spin_axis) or abs(spin_axis) < 0.2:
        return "neutre"
    left = spin_axis < 0
    is_lefty = str(hand).upper().startswith("L")
    if is_lefty:
        return "fade" if left else "draw"
    else:
        return "draw" if left else "fade"


def _driver_df(shots: pd.DataFrame, alias: str) -> pd.DataFrame:
    df = shots[shots["Alias"] == alias].copy()
    df = df[df.get("IsDriver", False) == True].copy()
    # numeric coercions used by charts
    for c in ["Carry", "Total", "Offline", "ClubSpeed", "BallSpeed", "Smash", "HLA", "VLA", "BackSpin", "SpinAxis", "SpinLat", "SpinTotal", "PeakHeight", "Desc Angle"]:
        if c in df.columns:
            df[c] = _num(df[c])
    return df


def _recompute_spins(df: pd.DataFrame) -> pd.DataFrame:
    if "BackSpin" in df.columns and "SpinAxis" in df.columns:
        back = _num(df["BackSpin"])
        axis = _num(df["SpinAxis"])
        axis_rad = np.deg2rad(axis)
        cosv = np.cos(axis_rad).replace(0, np.nan)
        spin_total = back / cosv
        spin_lat = spin_total * np.sin(axis_rad)
        df["SpinTotal"] = spin_total
        df["SpinLat"] = spin_lat
    return df


def _plot_dispersion(drv: pd.DataFrame, out_png: Path, hand: str):
    plot_df = drv.dropna(subset=["Carry", "Offline"]).copy()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.axhspan(-20, 20, alpha=0.15)
    ax.axhline(0, linewidth=1)
    ax.axvline(0, linewidth=1)
    # Color by Smash if available
    use_smash = "Smash" in plot_df.columns and plot_df["Smash"].notna().any()
    if use_smash:
        plot_df = plot_df.dropna(subset=["Smash"])
        sc = ax.scatter(plot_df["Carry"], plot_df["Offline"], c=plot_df["Smash"], s=28)
        cb = plt.colorbar(sc, ax=ax)
        cb.set_label("Smash")
    else:
        ax.scatter(plot_df["Carry"], plot_df["Offline"], s=28)

    ax.set_xlabel("Carry (m)")
    ax.set_ylabel("Offline (m)")
    ax.set_ylim(-50, 50)
    ax.set_title("Driver — Carry vs Offline (zone ±20 m)")

    # Ellipse 95% for decision-matrix metrics (optional)
    if ellipse_from_cov is not None and len(plot_df) >= 5:
        e95 = ellipse_from_cov(plot_df["Carry"].to_numpy(), plot_df["Offline"].to_numpy(), 0.95)
        if e95:
            from matplotlib.patches import Ellipse as MplEllipse
            ax.add_patch(MplEllipse((e95.cx, e95.cy), e95.width, e95.height, angle=e95.angle_deg,
                                    fill=False, linestyle="--", linewidth=2))
    _save(fig, out_png)

    bias = _safe_mean(plot_df["Offline"])
    in_fw = float(np.mean((np.abs(plot_df["Offline"]) <= 20).astype(float)) * 100.0) if len(plot_df) else 0.0
    # curvature tendency using SpinAxis when available
    if "SpinAxis" in plot_df.columns and plot_df["SpinAxis"].notna().any():
        avg_axis = _safe_mean(plot_df["SpinAxis"])
        curve = _curve_label(hand, avg_axis)
    else:
        avg_axis = float("nan")
        curve = "n/a"

    return {"n": int(len(plot_df)), "bias_off": bias, "pct_fw": in_fw, "avg_axis": avg_axis, "curve": curve}


def _plot_smash_efficiency(drv: pd.DataFrame, out_png: Path):
    plot_df = drv.dropna(subset=["Carry", "Smash"]).copy()
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.scatter(plot_df["Smash"], plot_df["Carry"], s=28)
    ax.set_xlabel("Smash factor")
    ax.set_ylabel("Carry (m)")
    ax.set_title("Efficacité d'impact — Smash vs Carry")
    _save(fig, out_png)


def _plot_launch(drv: pd.DataFrame, out_hla: Path, out_vla: Path):
    h = drv.dropna(subset=["Carry", "HLA"]).copy()
    v = drv.dropna(subset=["Carry", "VLA"]).copy()
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.scatter(h["Carry"], h["HLA"], s=28)
    ax.axhline(0, linewidth=1)
    ax.set_xlabel("Carry (m)")
    ax.set_ylabel("HLA (deg)")
    ax.set_title("Direction de lancement — HLA vs Carry")
    _save(fig, out_hla)

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.scatter(v["Carry"], v["VLA"], s=28)
    ax.set_xlabel("Carry (m)")
    ax.set_ylabel("VLA (deg)")
    ax.set_title("Hauteur de lancement — VLA vs Carry")
    _save(fig, out_vla)


def _plot_spin(drv: pd.DataFrame, out_png: Path, hand: str):
    plot_df = drv.dropna(subset=["Carry"]).copy()
    # Ensure spins computed
    plot_df = _recompute_spins(plot_df)
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    if "BackSpin" in plot_df.columns and plot_df["BackSpin"].notna().any():
        ax.scatter(plot_df["Carry"], plot_df["BackSpin"], s=26, label="BackSpin")
    if "SpinLat" in plot_df.columns and plot_df["SpinLat"].notna().any():
        ax.scatter(plot_df["Carry"], plot_df["SpinLat"], s=26, marker="^", label="Spin latéral")
        ax.axhline(0, linewidth=1)

    ax.set_xlabel("Carry (m)")
    ax.set_ylabel("Spin (rpm)")
    ax.set_title("Spin driver — backspin & latéral")
    ax.legend()
    _save(fig, out_png)


def _kpi_table(drv: pd.DataFrame):
    # Use "bons drives" for carry average: carry > 120m
    good = drv[drv["Carry"] > 120].copy() if "Carry" in drv.columns else drv.copy()

    rows = [
        ("Nb drives (total)", len(drv)),
        ("Nb drives (carry > 120m)", len(good)),
        ("Carry moyen (m) [>120m]", _safe_mean(good["Carry"]) if len(good) else float("nan")),
        ("Total moyen (m)", _safe_mean(drv["Total"]) if "Total" in drv.columns else float("nan")),
        ("Offline moyen (m)", _safe_mean(drv["Offline"]) if "Offline" in drv.columns else float("nan")),
        ("Offline (écart-type, m)", _safe_std(drv["Offline"]) if "Offline" in drv.columns else float("nan")),
        ("% dans ±20m", float(np.mean((drv["Offline"].abs()<=20).astype(float))*100.0) if "Offline" in drv.columns and len(drv) else float("nan")),
        ("ClubSpeed moyen (mph)", _safe_mean(drv["ClubSpeed"]) if "ClubSpeed" in drv.columns else float("nan")),
        ("BallSpeed moyen (mph)", _safe_mean(drv["BallSpeed"]) if "BallSpeed" in drv.columns else float("nan")),
        ("Smash moyen", _safe_mean(drv["Smash"]) if "Smash" in drv.columns else float("nan")),
        ("HLA moyen (deg)", _safe_mean(drv["HLA"]) if "HLA" in drv.columns else float("nan")),
        ("VLA moyen (deg)", _safe_mean(drv["VLA"]) if "VLA" in drv.columns else float("nan")),
        ("BackSpin moyen (rpm)", _safe_mean(drv["BackSpin"]) if "BackSpin" in drv.columns else float("nan")),
        ("SpinAxis moyen (deg)", _safe_mean(drv["SpinAxis"]) if "SpinAxis" in drv.columns else float("nan")),
        ("Peak Height moyen (m)", _safe_mean(drv["PeakHeight"]) if "PeakHeight" in drv.columns else float("nan")),
        ("Desc Angle moyen (deg)", _safe_mean(drv["Desc Angle"]) if "Desc Angle" in drv.columns else float("nan")),
    ]

    # Format
    out = []
    for k, v in rows:
        if isinstance(v, (int, np.integer)):
            out.append([k, str(int(v))])
        else:
            out.append([k, "n/a" if (v is None or (isinstance(v, float) and math.isnan(v))) else f"{v:.2f}"])
    return out


def _dominant_fault_comment(drv: pd.DataFrame, hand: str) -> str:
    if drv.empty or "Offline" not in drv.columns:
        return "Données insuffisantes pour qualifier un défaut dominant."
    off = drv["Offline"].dropna()
    if len(off) < 5:
        return "Peu de drives : le défaut dominant est encore instable. Accumule plus de données."
    bias = float(off.mean())
    spread = float(off.std(ddof=0))
    side = "droite" if bias > 0 else "gauche"
    # curvature using spin axis
    if "SpinAxis" in drv.columns and drv["SpinAxis"].notna().any():
        curve = _curve_label(hand, float(_safe_mean(drv["SpinAxis"])))
        curve_txt = f"Tendance de courbe : {curve}."
    else:
        curve_txt = "Spin axis non disponible : tendance de courbe non déterminée."
    return (
        f"Dispersion typique: écart-type offline ≈ {spread:.1f} m. "
        f"Biais moyen ≈ {bias:.1f} m ({side}). "
        f"{curve_txt} "
        f"Priorité: réduire le biais puis resserrer la dispersion."
    )


def _course_matrix_comment(stats: dict) -> str:
    n = stats.get("n", 0)
    if n == 0:
        return "Pas de données driver exploitables."
    bias = stats.get("bias_off", 0.0)
    pct = stats.get("pct_fw", 0.0)
    side = "droite" if bias > 2 else ("gauche" if bias < -2 else "centré")
    if pct >= 60:
        lvl = "confortable"
    elif pct >= 40:
        lvl = "moyen"
    else:
        lvl = "risqué"
    # Decision rule: aim offset opposite the bias by ~half the bias
    aim = -bias * 0.5
    return (
        f"Lecture parcours: dispersion {lvl} (≈ {pct:.0f}% dans ±20 m). "
        f"Biais {side} (≈ {bias:.1f} m). "
        f"Décision simple: viser ~{aim:.1f} m vers le côté opposé au biais, "
        f"et choisir des lignes qui évitent le 'grand miss' (bord externe de l'ellipse 95%)."
    )


def build_modelB_gold(shots_df: pd.DataFrame, alias: str, hand: str, session_date: str, out_pdf: str) -> str:
    drv = _driver_df(shots_df, alias)
    drv = _recompute_spins(drv)

    out_path = Path(out_pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    workdir = out_path.parent

    # Figures
    f_disp = workdir / f"modelB_{alias}_disp.png"
    f_eff = workdir / f"modelB_{alias}_eff.png"
    f_hla = workdir / f"modelB_{alias}_hla.png"
    f_vla = workdir / f"modelB_{alias}_vla.png"
    f_spin = workdir / f"modelB_{alias}_spin.png"

    stats = _plot_dispersion(drv, f_disp, hand)
    _plot_smash_efficiency(drv, f_eff)
    _plot_launch(drv, f_hla, f_vla)
    _plot_spin(drv, f_spin, hand)

    styles = getSampleStyleSheet()
    story = []

    # Cover / header
    story.append(Paragraph("<b>MODEL B (GOLD) — Driver only</b>", styles["Title"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"<b>Date de la session :</b> {session_date}", styles["Normal"]))
    story.append(Paragraph(f"<b>Nom / alias :</b> {alias}", styles["Normal"]))
    story.append(Paragraph(f"<b>Dextérité :</b> {_hand_label(hand)}", styles["Normal"]))
    story.append(Paragraph(f"<b>Nb drives :</b> {int(len(drv))}", styles["Normal"]))
    story.append(PageBreak())

    # 1) KPIs
    story.append(Paragraph("1) Indicateurs clés Driver", styles["Heading1"]))
    kpi = _kpi_table(drv)
    t = Table([["KPI", "Valeur"]] + kpi, colWidths=[280, 160])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(1,0), colors.HexColor("#f2f2f2")),
        ("GRID",(0,0),(-1,-1), 0.5, colors.HexColor("#dddddd")),
        ("FONTNAME",(0,0),(-1,0), "Helvetica-Bold"),
        ("FONTNAME",(0,1),(-1,-1), "Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1), 9),
        ("VALIGN",(0,0),(-1,-1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Lecture: le carry moyen est calculé sur les drives avec carry > 120 m (bons drives), "
        "pour éviter que les tops/ratés ne biaisent le niveau réel.",
        styles["BodyText"]
    ))
    story.append(PageBreak())

    # 2) Dispersion
    story.append(Paragraph("2) Dispersion & contrôle de trajectoire", styles["Heading1"]))
    story.append(Image(str(f_disp), width=7.2*inch, height=4.2*inch))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Analyse: {stats['pct_fw']:.0f}% des drives finissent dans la zone ±20 m. "
        f"Biais moyen offline ≈ {stats['bias_off']:.1f} m. "
        + (f"Spin axis moyen ≈ {stats['avg_axis']:.1f}° → tendance {stats['curve']}." if np.isfinite(stats.get("avg_axis", np.nan)) else ""),
        styles["BodyText"]
    ))
    story.append(PageBreak())

    # 3) Efficiency
    story.append(Paragraph("3) Efficacité d'impact (Smash)", styles["Heading1"]))
    story.append(Image(str(f_eff), width=7.2*inch, height=3.6*inch))
    story.append(Spacer(1, 6))
    sm = _safe_mean(drv["Smash"]) if "Smash" in drv.columns else float("nan")
    cs = _safe_mean(drv["ClubSpeed"]) if "ClubSpeed" in drv.columns else float("nan")
    comment = (
        f"Analyse: smash moyen ≈ {sm:.2f}. "
        "Objectif: stabiliser le centrage (contact) pour augmenter le carry à vitesse constante. "
        "Si le smash varie beaucoup d'un coup à l'autre, priorité au point d'impact (face) et au tempo."
        if np.isfinite(sm) else
        "Analyse: smash indisponible (vitesses manquantes). Vérifie Ball Speed / Club Speed dans le CSV."
    )
    story.append(Paragraph(comment, styles["BodyText"]))
    story.append(PageBreak())

    # 4) Launch
    story.append(Paragraph("4) Angles de lancement (HLA / VLA)", styles["Heading1"]))
    story.append(Image(str(f_hla), width=7.2*inch, height=3.6*inch))
    story.append(Spacer(1, 10))
    story.append(Image(str(f_vla), width=7.2*inch, height=3.6*inch))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Analyse: HLA te dit où la balle démarre (direction initiale), VLA influence la fenêtre de vol. "
        "Recherche une direction initiale plus stable (HLA proche de 0) avant de chercher plus de hauteur.",
        styles["BodyText"]
    ))
    story.append(PageBreak())

    # 5) Spin
    story.append(Paragraph("5) Spin — cohérence et tendance", styles["Heading1"]))
    story.append(Image(str(f_spin), width=7.2*inch, height=3.6*inch))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Analyse: le backspin pilote la portance, le spin latéral la courbure. "
        "Une courbure trop marquée et variable indique souvent une face instable à l'impact. "
        "Objectif: réduire la variabilité du spin latéral plutôt que de 'forcer' une trajectoire.",
        styles["BodyText"]
    ))
    story.append(PageBreak())

    # 6) Dominant fault profile
    story.append(Paragraph("6) Profil de défaut dominant", styles["Heading1"]))
    story.append(Paragraph(_dominant_fault_comment(drv, hand), styles["BodyText"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Drill recommandé (10 min): 1) 'tee gate' (2 tees devant la balle) pour valider la face, "
        "2) 5 swings à 70% vitesse en visant la même fenêtre (HLA), 3) 5 swings 'full' en gardant la même routine.",
        styles["BodyText"]
    ))
    story.append(PageBreak())

    # 7) Course decision matrix
    story.append(Paragraph("7) Matrice de décision parcours", styles["Heading1"]))
    story.append(Paragraph(_course_matrix_comment(stats), styles["BodyText"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Règle terrain: si le trou est étroit, privilégier la stratégie 'éviter le grand miss' "
        "(viser au centre élargi / choisir un départ moins risqué) plutôt que chercher la distance maximale.",
        styles["BodyText"]
    ))
    story.append(PageBreak())

    # 8) 2-month plan
    story.append(Paragraph("8) Plan d'entraînement (objectif 2 mois)", styles["Heading1"]))
    story.append(Paragraph(
        "Objectif 2 mois (driver): +10% de balles dans ±20 m et +5 à +10 m de carry moyen (sur drives >120 m), "
        "sans augmenter la dispersion. "
        "Axes: (1) contact/smash, (2) direction initiale (HLA), (3) contrôle spin latéral.",
        styles["BodyText"]
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "<b>Semaine type (2 séances / semaine)</b><br/>"
        "Séance A (30–40 min): 10 balles tempo 70% + 15 balles 'tee gate' + 10 balles cibles (HLA).<br/>"
        "Séance B (30–40 min): 10 balles 'start line' (HLA) + 15 balles dispersion (zone ±20) + 10 balles routine parcours.<br/>"
        "<b>Progrès attendus</b>: smash plus stable, offline std ↓, %±20 ↑, spin latéral moins variable.",
        styles["BodyText"]
    ))

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    doc.build(story)
    return str(out_path)
