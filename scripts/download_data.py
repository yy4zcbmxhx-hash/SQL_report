"""Download the exact input revision; no credentials or mutable main branch."""
import hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
COMMIT='0aa053d1fc9e1bcea0ac95bba234e4e781a2aab5'
manifest=json.loads((ROOT/'originals/manifest.json').read_text())
for name in ['dim_customers.csv','dim_products.csv','fact_sales.csv']:
    target=ROOT/'originals'/name
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==manifest[name]['sha256']:continue
    with urllib.request.urlopen(f'https://raw.githubusercontent.com/yy4zcbmxhx-hash/SQL_report/{COMMIT}/{name}',timeout=60) as response:data=response.read()
    assert hashlib.sha256(data).hexdigest()==manifest[name]['sha256'], f'Checksum mismatch: {name}'
    target.write_bytes(data)
    print(name,'verified')
