ModelA GOLD (addon + generator.py patched)

Contains:
- generator.py (patched): DOES NOT change your Base logic. Adds ModelA_GOLD PDF generation.
- core/metrics.py, pdf/theme.py, models/modelA_gold.py

Install:
1) Copy generator.py + folders core/, pdf/, models/ into your repo root.
2) Ensure app.py calls generator.generate_all(..., filenames=[uf.name for uf in uploads]) so alias mapping works.
