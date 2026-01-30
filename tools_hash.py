import streamlit as st
import bcrypt

st.set_page_config(page_title="Tools – Hash", layout="centered")

st.title("Générer un hash bcrypt (coach)")

pwd = st.text_input("Mot de passe à hasher", type="password")
confirm = st.text_input("Confirmer", type="password")

if st.button("Générer"):
if not pwd:
st.error("Mot de passe vide.")
elif pwd != confirm:
st.error("Les deux champs ne correspondent pas.")
else:
h = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
st.success("Hash généré (copie-colle dans Streamlit Secrets)")
st.code(h)
