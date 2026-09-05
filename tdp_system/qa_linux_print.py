"""Render synthetic acceptance workbooks with the deployed Linux PDF renderer."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import uuid
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--local-renderer', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    cli = str(Path(os.environ['APPDATA']) / 'npm/railway.cmd')
    remote = '/tmp/tdp-print-acceptance-' + uuid.uuid4().hex
    def execute(code, timeout=60):
        encoded = base64.b64encode(code.encode()).decode()
        command = 'python -c "import base64;exec(base64.b64decode(\'' + encoded + '\'))"'
        run = subprocess.run([cli, 'ssh', command], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
        if run.returncode: raise RuntimeError('Railway QA SSH failed: ' + run.stderr[-1000:])
        return run.stdout
    from .verify_round4_artifacts import sample_books
    books = sample_books()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        if args.local_renderer:
            bundle.writestr('qa_renderer.py', Path(__file__).with_name('excel_print_renderer.py').read_bytes())
        for name, book in books:
            stream = io.BytesIO(); book.save(stream); book.close()
            bundle.writestr(name, stream.getvalue())
            (output / name).write_bytes(stream.getvalue())
    encoded = base64.b64encode(archive.getvalue()).decode()
    execute(f"from pathlib import Path; p=Path('{remote}');p.mkdir();(p/'upload.b64').write_text('')")
    for offset in range(0, len(encoded), 3000):
        execute(f"from pathlib import Path; p=Path('{remote}/upload.b64');f=p.open('a');f.write('{encoded[offset:offset+3000]}');f.close()")
    print('Synthetic workbooks uploaded to temporary QA directory', flush=True)
    code = f"""
from pathlib import Path
import base64,io,json,zipfile
from tdp_system.excel_print_renderer import build_excel_pdf_bundle
root=Path('{remote}')
sources=[]
with zipfile.ZipFile(io.BytesIO(base64.b64decode((root/'upload.b64').read_text()))) as archive:
 for name in archive.namelist():
  if name == 'qa_renderer.py':
   import importlib.util
   module_path=root/name;module_path.write_bytes(archive.read(name))
   spec=importlib.util.spec_from_file_location('qa_renderer',module_path)
   module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   build_excel_pdf_bundle=module.build_excel_pdf_bundle
   continue
  assert Path(name).name==name and name.endswith('.xlsx')
  target=root/name;target.write_bytes(archive.read(name))
  sources.append({{'path':target,'document_type':'acceptance','title':name}})
result=build_excel_pdf_bundle(sources,root/'acceptance.pdf',paper='A4')
print('TDP_QA:'+json.dumps(result))
"""
    raw = execute(code, timeout=240)
    result = json.loads(next(line.removeprefix('TDP_QA:') for line in raw.splitlines() if line.startswith('TDP_QA:')))
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    payload = execute(f"from pathlib import Path;import base64;print('TDP_QA:'+base64.b64encode(Path('{remote}/acceptance.pdf').read_bytes()).decode())")
    pdf = base64.b64decode(next(line.removeprefix('TDP_QA:') for line in payload.splitlines() if line.startswith('TDP_QA:')))
    (output / 'acceptance.pdf').write_bytes(pdf)
    assert result['section_count'] == 7 and result['pages'] == 7, 'Sample documents must render exactly seven selected sheets, once each'
    assert all(section['pages'] == 1 for section in result['sections']), 'A sample section included another sheet'
    import fitz
    with fitz.open(stream=pdf, filetype='pdf') as document:
        for index, page in enumerate(document):
            page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25)).save(str(output / f'page-{index+1}.png'))
    print(json.dumps({'ok':result['ok'],'pages':result['pages'],'sections':result['section_count'],'output':str(output)}))


if __name__ == '__main__': main()
