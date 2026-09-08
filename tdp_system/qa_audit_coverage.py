"""Produce route evidence without treating endpoint reachability as full coverage."""
import argparse
import csv
import json
from pathlib import Path
import re

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--routes',type=Path,required=True)
    p.add_argument('--regression',type=Path,required=True)
    p.add_argument('--surface',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    routes=json.loads(a.routes.read_text(encoding='utf8'))['routes']
    regression=json.loads(a.regression.read_text(encoding='utf8'))
    surface=json.loads(a.surface.read_text(encoding='utf8'))
    rows=[]
    for route in routes:
        pattern='^'+re.sub(r'<(?:(int|path|string):)?[^>]+>',lambda m: r'\d+' if m[1]=='int' else '.+' if m[1]=='path' else '[^/]+',route['route'])+'$'
        for method in route['methods']:
            hits=[(m['module'],r) for m in regression['modules'] for r in m.get('http_routes',[]) if r['route']==route['route'] and r['method']==method]
            hosted=[r for r in surface['requests'] if r['method']==method and re.match(pattern,r['path'])]
            rows.append({'method':method,'route':route['route'],'endpoint':route['endpoint'],
                         'unit_modules':'; '.join(sorted(set(m for m,r in hits))),
                         'unit_statuses':'; '.join(map(str,sorted(set(r['status'] for m,r in hits)))),
                         'hosted_read_statuses':'; '.join(map(str,sorted(set(r['status'] for r in hosted)))),
                         'evidence':'HTTP exercised; behavior must be assessed by case' if hits or hosted else 'No HTTP evidence in these two runs'})
    with (a.output/'routes.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    controls=[]
    for screen in surface['screens']:
        unique={}
        for control in screen['controls']:
            if not control['visible']:continue
            key=(control['action'],control['id'],control['name'],control['tag'])
            if not any(key[:3]):continue
            unique[key]={'screen':screen['name'],**{k:control[k] for k in ['action','id','name','tag','disabled']},'evidence':'Visible only; not proof of interaction'}
        controls.extend(unique.values())
    with (a.output/'visible-controls.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=controls[0]);writer.writeheader();writer.writerows(controls)
    summary={'route_methods':len(rows),'with_http_evidence':sum(bool(r['unit_modules'] or r['hosted_read_statuses']) for r in rows),
             'without_http_evidence':[{'method':r['method'],'route':r['route']} for r in rows if not(r['unit_modules'] or r['hosted_read_statuses'])],
             'visible_control_instances_after_dedup_by_screen':len(controls),'scope_note':'Includes legacy and audit routes. Reachability is not full workflow coverage.'}
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    print(json.dumps(summary))

if __name__=='__main__':main()
