import streamlit as st
import bcrypt

def _get_secrets():
    sec = st.secrets
    return {
        "coach_users": list(sec["auth"].get("coach_users", [])),
        "coach_hashes": list(sec["auth"].get("coach_hashes", [])),
        "student_users": list(sec["auth"].get("student_users", [])),
        "student_hashes": list(sec["auth"].get("student_hashes", [])),
    }

def verify_password(username: str, password: str) -> tuple[bool,str]:
    s = _get_secrets()
    if username in s["coach_users"]:
        idx = s["coach_users"].index(username)
        ok = bcrypt.checkpw(password.encode("utf-8"), s["coach_hashes"][idx].encode("utf-8"))
        return ok, "coach" if ok else ""
    if username in s["student_users"]:
        idx = s["student_users"].index(username)
        ok = bcrypt.checkpw(password.encode("utf-8"), s["student_hashes"][idx].encode("utf-8"))
        return ok, "student" if ok else ""
    return False, ""

def require_login():
    if "role" not in st.session_state:
        st.session_state.role = ""
    if "user" not in st.session_state:
        st.session_state.user = ""

    if st.session_state.role:
        return

    st.title("CoachingGolf — Login")
    username = st.text_input("Utilisateur", placeholder="coach / Licornekeeper / Sportsman / Cyberman")
    password = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter", type="primary"):
        ok, role = verify_password(username, password)
        if ok:
            st.session_state.role = role
            st.session_state.user = username
            st.success("Connecté.")
            st.rerun()
        else:
            st.error("Login ou mot de passe incorrect.")

def logout_button():
    if st.button("Se déconnecter"):
        st.session_state.role = ""
        st.session_state.user = ""
        st.rerun()
