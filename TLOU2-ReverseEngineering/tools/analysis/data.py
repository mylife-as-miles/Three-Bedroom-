"""Load public JSON or its gzip companion (descriptor files are resolved)."""
import gzip,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name):
 p=ROOT/'databases'/name
 if p.exists():
  value=json.load(p.open())
  if not isinstance(value,dict) or value.get('storage')!='gzip-json':return value
  p=p.parent/value['file']
 else:p=Path(str(p)+'.gz')
 return json.load(gzip.open(p,'rt'))
