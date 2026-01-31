# CoachingGolf Portal — V1 (Streamlit Cloud + Google Drive)

## What you get (V1)
- One portal with login
- Coach/Admin page: upload CSVs -> auto-detect session date from CSV column `date` -> build/update Base Excel -> generate PDFs Models A→H
- Student page: browse sessions -> preview/download PDFs
- Drive storage: all outputs are stored in your Google Drive folder `CoachingGolf`

## Key rules (frozen)
- Session date comes ONLY from CSV column `date` (not filename)
- Aliases: Conre→Sportsman, Treve/Trêve→Cyberman, Licornekeeper stays
- Model H includes:
  - H1 inter-session comparison
  - H2 gapping (good shots carry in [Q20;Q95], minimum 20 good shots), with σ Carry (not variance), offline signed + abs

## 0) Create Drive folder structure
Create a folder `CoachingGolf` then subfolders:
- Base/
- Uploads/
- Eleves/
- Groupe/

## 1) Create a Google Service Account and share the Drive folder
- Create service account in Google Cloud Console
- Share the `CoachingGolf` folder with the service account email
- Copy the folder ID (from Drive URL) into secrets

## 2) Deploy on Streamlit Cloud
- Put this repo on GitHub
- Streamlit Cloud: New app -> select repo -> set secrets
- App entrypoint: app.py

## 3) Plug your existing PDF generator
This V1 provides the full ingestion + storage + UI.
You must plug your real models generator in `generator.py`:
- `generate_models_for_session(base_df, roster, session_date, out_dir)` should create PDFs ModelA..ModelH
If you already have a script, call it from that function.

## Local run
```bash
pip install -r requirements.txt
streamlit run app.py
```

## V1.1 (patched) — What’s included
- app.py patched to upload:
  - student PDFs -> Eleves/<alias>/<session_date>/
  - group PDFs   -> Groupe/<session_date>/
- generator.py returns the required structure:
  - base_xlsx, student_pdfs, group_pdfs
- Frozen Model H upgrade:
  - adds gapping module (good shots carry in [Q20;Q95], threshold=20), σ Carry, offline signed+abs, spins, VLA, peak height
  - coach commentary style: mixed analytic + course decision

## Models routing (V1.1)
- Students: ModelA, ModelB, ModelC_ELEVE, ModelE, ModelH_ELEVE
- Group: ModelC_GROUPE, ModelD, ModelF, ModelG, ModelH_GROUPE
