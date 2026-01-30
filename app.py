import streamlit as st
import pandas as pd
import json
import tempfile
from pathlib import Path
from auth import require_login, logout_button
from roster import load_roster, to_alias, hand_of
from ingest import session_date_from_csv, detect_player_name
import generator
import drive_storage as ds

st.set_page_config(page_title="CoachingGolf Portal", layout="wide")

# require_login() # desactiver temporairement

roster = load_roster("roster.json")
# drive_root = st.secrets["app"]["drive_root_folder_id"]
# base_filename = st.secrets["app"].get("base_filename","Base_Coaching_Golf.xlsx")

role = st.session_state.role
user = st.session_state.user

with st.sidebar:
    st.write(f"**Connecté**: {user} ({role})")
    page = st.radio("Navigation", ["Élève", "Coach", "Admin"] if role=="coach" else ["Élève"])
    logout_button()

def drive_paths_for_session(session_date: str, alias: str|None=None):
    service = ds._client()
    base_id = ds.ensure_folder(service, drive_root, "Base")
    uploads_id = ds.ensure_folder(service, drive_root, "Uploads")
    eleves_id = ds.ensure_folder(service, drive_root, "Eleves")
    groupe_id = ds.ensure_folder(service, drive_root, "Groupe")

    # session folders
    up_sess = ds.ensure_folder(service, uploads_id, session_date)
    grp_sess = ds.ensure_folder(service, groupe_id, session_date)

    stu_sess = None
    if alias:
        stu = ds.ensure_folder(service, eleves_id, alias)
        stu_sess = ds.ensure_folder(service, stu, session_date)
    return {"Base":base_id,"Uploads":up_sess,"Groupe":grp_sess,"Eleve":stu_sess}

def list_sessions_for_alias(alias: str):
    service = ds._client()
    eleves_id = ds.ensure_folder(service, drive_root, "Eleves")
    stu_id = ds.ensure_folder(service, eleves_id, alias)
    files = ds.list_children(stu_id)
    # folders only
    sess = sorted([f["name"] for f in files if f["mimeType"]=="application/vnd.google-apps.folder"], reverse=True)
    return sess

def list_pdfs_in_folder(folder_id: str):
    files = ds.list_children(folder_id)
    pdfs = [f for f in files if f["mimeType"]=="application/pdf"]
    pdfs.sort(key=lambda x: x["name"])
    return pdfs

def show_student(alias: str):
    st.title(f"Espace élève — {alias}")
    sessions = list_sessions_for_alias(alias)
    if not sessions:
        st.info("Aucune session disponible.")
        return
    sess = st.selectbox("Session", sessions)
    service = ds._client()
    eleves_id = ds.ensure_folder(service, drive_root, "Eleves")
    stu_id = ds.ensure_folder(service, eleves_id, alias)
    sess_id = ds.ensure_folder(service, stu_id, sess)
    pdfs = list_pdfs_in_folder(sess_id)

    st.subheader("Rapports PDF")
    if not pdfs:
        st.warning("Pas de PDF trouvés pour cette session.")
    else:
        for f in pdfs:
            st.write(f"• {f['name']}")
            st.link_button("Ouvrir dans Drive", f["webViewLink"])

    st.caption("V1: les PDFs sont stockés dans Drive; la prévisualisation inline peut être ajoutée ensuite.")

def show_coach():
    st.title("Espace coach — Vue globale")
    st.write("V1: liste les dossiers élèves + sessions + PDFs.")
    service = ds._client()
    eleves_id = ds.ensure_folder(service, drive_root, "Eleves")
    students = [f for f in ds.list_children(eleves_id) if f["mimeType"]=="application/vnd.google-apps.folder"]
    students.sort(key=lambda x: x["name"])
    if not students:
        st.info("Aucun élève.")
        return
    col1,col2 = st.columns([1,2])
    with col1:
        alias = st.selectbox("Élève", [s["name"] for s in students])
    with col2:
        st.write("")
    show_student(alias)

def show_admin():
    st.title("Admin — Upload CSV & génération A→H")
    st.info("Générateur attendu: out['student_pdfs'] + out['group_pdfs'] (voir README).")
    uploads = st.file_uploader("Dépose 1 à 10 CSV (une session)", type=["csv"], accept_multiple_files=True)
    if not uploads:
        st.stop()

    csv_dfs=[]
    raw_names=[]
    session_dates=[]
    for uf in uploads:
        df = pd.read_csv(uf)
        csv_dfs.append(df)
        raw_names.append(detect_player_name(df, uf.name))
        session_dates.append(session_date_from_csv(df))

    # Validate session date consistency
    uniq = sorted(set(session_dates))
    if len(uniq) > 1:
        st.error(f"Les CSV contiennent plusieurs dates de session: {uniq}. V1 demande une seule session à la fois.")
        st.stop()

    session_date = uniq[0]
    st.success(f"Date de session détectée (champ 'date' CSV): {session_date}")

    # Map to aliases
    aliases=[to_alias(n, roster) for n in raw_names]
    st.write("Joueurs détectés → alias:")
    st.table(pd.DataFrame({"Nom détecté":raw_names, "Alias":aliases}))

    if st.button("Générer Base + Models A→H", type="primary"):
        with tempfile.TemporaryDirectory() as td:
            out = generator.generate_all(csv_dfs, roster, session_date, td)

            # Upload to Drive
            paths = drive_paths_for_session(session_date)
            service = ds._client()
            base_id = ds.ensure_folder(service, drive_root, "Base")

            # Base upload (stable name + archive)
            ds.upload_file(base_id, out["base_xlsx"], filename=base_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            ds.upload_file(base_id, out["base_xlsx"], filename=f"Base_Coaching_Golf_{session_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # Upload raw CSV archives
            up_id = paths["Uploads"]
            for uf in uploads:
                ds.upload_bytes(up_id, uf.name, uf.getvalue(), "text/csv")

            # --- Upload PDFs: Students + Group (NEW) ---
            service = ds._client()
            eleves_id = ds.ensure_folder(service, drive_root, "Eleves")
            groupe_id = ds.ensure_folder(service, drive_root, "Groupe")

            # Ensure session folders
            grp_sess_id = ds.ensure_folder(service, groupe_id, session_date)

            # 1) Group PDFs
            for pdf in out.get("group_pdfs", []):
                ds.upload_file(grp_sess_id, pdf, filename=Path(pdf).name, mime="application/pdf")

            # 2) Student PDFs
            student_pdfs = out.get("student_pdfs", {})
            for alias, pdf_list in student_pdfs.items():
                stu_id = ds.ensure_folder(service, eleves_id, alias)
                stu_sess_id = ds.ensure_folder(service, stu_id, session_date)
                for pdf in pdf_list:
                    ds.upload_file(stu_sess_id, pdf, filename=Path(pdf).name, mime="application/pdf")

        st.success("Génération terminée. Vérifie le Drive.")

if page == "Élève":
    # students only see their own alias
    if role == "student":
        show_student(user)
    else:
        # coach can preview any student from student page
        show_student(st.selectbox("Choisir un élève", ["Licornekeeper","Sportsman","Cyberman"]))
elif page == "Coach":
    show_coach()
elif page == "Admin":
    show_admin()
