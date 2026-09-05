"""Exercise the packaged EXE twice, with isolated DB, port and offline connectors."""
import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
from contextlib import closing
from pathlib import Path
from urllib.request import Request, urlopen

import psutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('exe', type=Path)
    parser.add_argument('--port', type=int, default=18819)
    args = parser.parse_args()
    root = Path(tempfile.mkdtemp(prefix='tdp-release-20260905-')).resolve()
    runtime = root / 'Thanh_Dat_Phat.exe'
    shutil.copy2(args.exe, runtime)
    data = root / 'data'; data.mkdir()
    exports = root / 'exports'; exports.mkdir()
    env = os.environ.copy()
    offline = {'MSMI_API_BASE_URL':'http://127.0.0.1:9', 'MSMI_API_TOKEN':'isolated',
               'MINVOICE_API_BASE_URL':'http://127.0.0.1:9', 'MINVOICE_USERNAME':'isolated',
               'MINVOICE_PASSWORD':'isolated'}
    env.update(offline)
    env.update(TDP_DATA_DIR=str(data), TDP_EXPORT_DIR=str(exports), TDP_DB_PATH=str(data/'tdp.sqlite3'),
               TDP_PORT=str(args.port), TDP_ALLOW_LAN='0', TDP_SMOKE_INSTANCE_ID='release-20260905')
    (root / '.env').write_text('\n'.join(f'{k}={v}' for k,v in offline.items()), encoding='utf-8')

    def request(path, body=None):
        req = Request(f'http://127.0.0.1:{args.port}'+path,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={'Content-Type':'application/json'} if body is not None else {})
        with urlopen(req, timeout=30) as response:
            return response.read()

    def get(path, body=None):
        result=json.loads(request(path,body))
        assert result.get('ok'), 'API failed: '+path
        return result

    def stop(process):
        # Only descendants/listeners whose executable is our copied smoke EXE.
        for candidate in psutil.process_iter(['pid','exe']):
            try:
                if candidate.info['exe'] and Path(candidate.info['exe']).resolve() == runtime:
                    candidate.terminate()
            except (psutil.Error, OSError):
                pass
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)
        time.sleep(.5)

    for attempt in (1,2):
        with socket.socket() as probe:
            assert probe.connect_ex(('127.0.0.1',args.port)) != 0, 'Smoke port already occupied'
        with (root/f'stdout-{attempt}.log').open('wb') as out, (root/f'stderr-{attempt}.log').open('wb') as err:
            process=subprocess.Popen([str(runtime),'--no-browser','--smoke-test-instance'],cwd=root,env=env,
                                     stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline=time.monotonic()+150
                while True:
                    assert process.poll() is None, 'EXE exited before health; inspect isolated log'
                    try:
                        health=get('/health'); break
                    except (OSError,ValueError):
                        if time.monotonic()>deadline: raise RuntimeError('Packaged health timeout: '+str(root))
                        time.sleep(.3)
                assert health.get('database_ready') and health.get('schema_ready') and health.get('integrity')=='ok'
                print(f'EXE start {attempt}: health/schema/integrity PASS', flush=True)
                bootstrap=get('/api/bootstrap')
                nav=request('/').decode().split('<nav id="nav">')[1].split('</nav>')[0]
                assert all(f'data-view="{v}"' not in nav for v in ('deliveries','kitchen','payroll'))
                assert 'data-view="physical"' in nav
                script=request('/static/app.js').decode()
                assert '/api/backup/status' in script and '&active_only=1' in script
                assert 'Đoàn Văn Giang' not in bootstrap['master']['eligible_sellers']
                assert 'Nguyễn Văn Toại' not in bootstrap['master']['eligible_sellers']
                status=get('/api/backup/status')
                assert status['last_success'] and not status['error'], 'Packaged backup failed'
                with closing(sqlite3.connect(data/'auto_backups'/status['filename'])) as backup:
                    assert backup.execute('PRAGMA quick_check').fetchone()[0]=='ok'
                assert len(request('/api/bk-import/template')) > 1000
                if attempt == 1:
                    selected=next(((b,n) for b in bootstrap['batches'] for n in b.get('delivery_notes',[])),None)
                    if selected:
                        batch,note=selected
                        preview=get('/api/documents/preview',{'kind':'deliveries','selections':[{'batch_id':batch['id'],'kitchen':note['code']}]})
                        assert preview['sheet_count'] > 0
                        assert len(request('/api/documents/'+preview['token']+'/excel?sheets=0'))>1000
                        print('Packaged delivery preview and Excel PASS',flush=True)
                else:
                    with closing(sqlite3.connect(data/'tdp.sqlite3')) as check:
                        assert check.execute("SELECT value FROM settings WHERE key='release_preserve_marker'").fetchone()[0]=='keep-customer-data'
                    assert list((data/'migration_backups').glob('*.sqlite3'))
                    print('Restart preserves existing DB and migration backup PASS',flush=True)
            finally:
                stop(process)
        if attempt==1:
            with closing(sqlite3.connect(data/'tdp.sqlite3')) as check:
                check.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('release_preserve_marker','keep-customer-data')")
                check.commit()
    result={'ok':True,'exe':str(args.exe.resolve()),'isolated_dir':str(root),
            'checks':['two_startups','schema','integrity','compact_menu','seller_exclusion','automatic_backup',
                      'template_download','existing_data_preserved','pre_migration_backup'],
            'live_connector_calls':False,'customer_database_modified':False}
    (root/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
