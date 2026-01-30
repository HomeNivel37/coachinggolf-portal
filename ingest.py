import re
from datetime import datetime

def _to_yyyy_mm_dd(value):
if value is None:
return None
s = str(value).strip()
if not s:
return None

formats = [
"%Y-%m-%d",
"%d/%m/%Y",
"%m/%d/%Y",
"%Y/%m/%d",
"%d-%m-%Y",
"%m-%d-%Y",
]

for fmt in formats:
try:
return datetime.strptime(s[:10], fmt).strftime("%Y-%m-%d")
except Exception:
pass

match = re.search(r"(20\d{2})[-/](\d{2})[-/](\d{2})", s)
if match:
y, m, d = match.groups()
return f"{y}-{m}-{d}"

return None


def session_date_from_csv(df, filename=None):
candidates = [
"date",
"Date",
"Round Date",
"RoundDate",
"Session Date",
"SessionDate",
]

for col in candidates:
if col in df.columns:
parsed = _to_yyyy_mm_dd(df[col].iloc[0])
if parsed:
return parsed

if filename:
match = re.search(r"(20\d{2}-\d{2}-\d{2})", filename)
if match:
return match.group(1)

return datetime.today().strftime("%Y-%m-%d")


def detect_player_name(filename: str):
name = filename.lower()
if "licorne" in name:
return "Licornekeeper"
if "conre" in name:
return "Sportsman"
if "treve" in name:
return "Cyberman"
return "Unknown"
