"""Refresh authored snapshot. Build with installed Data runtime or npm run build afterwards."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'dashboard/src/data.json'
previous=json.loads(p.read_text())
current=json.loads((ROOT/'outputs/dashboard_snapshot.json').read_text())
current['id']=previous['id']
current['buildStatus']='complete'
p.write_text(json.dumps(current,ensure_ascii=False,indent=2))
print('Authored snapshot updated; rebuild dashboard before viewing new results.')
