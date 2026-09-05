"""Run regression modules with separate databases and offline connector defaults."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--module')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.module:
        for name in ('data', 'exports', 'temp'):
            (output / name).mkdir(exist_ok=True)
        os.environ.update(TDP_DATA_DIR=str(output / 'data'), TDP_DB_PATH=str(output / 'data/default.sqlite3'),
                          TDP_EXPORT_DIR=str(output / 'exports'), TEMP=str(output / 'temp'), TMP=str(output / 'temp'),
                          MSMI_API_BASE_URL='http://127.0.0.1:9', MSMI_API_TOKEN='offline-test',
                          MINVOICE_API_BASE_URL='http://127.0.0.1:9', MINVOICE_USERNAME='offline-test',
                          MINVOICE_PASSWORD='offline-test')
        from . import server
        server.connector_config_paths = lambda: []
        suite = unittest.defaultTestLoader.loadTestsFromName('tdp_system.' + args.module)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary = {'module': args.module, 'tests': result.testsRun, 'failures': len(result.failures),
                   'errors': len(result.errors), 'skipped': len(result.skipped), 'ok': result.wasSuccessful()}
        (output / 'result.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        return 0 if result.wasSuccessful() else 1
    modules = sorted(p.stem for p in Path(__file__).parent.glob('test_*.py'))
    def run(module):
        directory = output / module
        directory.mkdir(exist_ok=True)
        start = time.monotonic()
        with (directory / 'tests.log').open('wb') as log:
            process = subprocess.run([sys.executable, '-m', 'tdp_system.qa_railway_acceptance',
                                      '--output', str(directory), '--module', module],
                                     stdout=log, stderr=log, timeout=600,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        result_file = directory / 'result.json'
        summary = json.loads(result_file.read_text(encoding='utf-8')) if result_file.exists() else {
            'module': module, 'ok': False, 'exit_code': process.returncode}
        summary['seconds'] = round(time.monotonic() - start, 1)
        print(json.dumps(summary), flush=True)
        return summary
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(run, modules))
    summary = {'ok': all(r['ok'] for r in results), 'modules': results,
               'tests': sum(r.get('tests', 0) for r in results)}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    return 0 if summary['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
