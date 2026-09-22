"""Use the packaged DOCX rasterizer with a Microsoft Word PDF export on Windows."""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parent
temporary = root / 'temp'
temporary.mkdir(exist_ok=True)
tempfile.tempdir = str(temporary)
runtime = Path(r'C:\Users\bhagyaraj\.cache\codex-runtimes\codex-primary-runtime\dependencies')
poppler = next((runtime/'native'/'poppler').rglob('pdftoppm.exe')).parent
os.environ['PATH'] = str(poppler) + os.pathsep + os.environ['PATH']
renderer = Path(r'C:\Users\bhagyaraj\.codex\plugins\cache\openai-primary-runtime\documents\26.904.11930\skills\documents\render_docx.py')
spec = importlib.util.spec_from_file_location('render_docx', renderer)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
pdf = str(Path(sys.argv[2]).resolve())
module.convert_to_pdf = lambda *args, **kwargs: (pdf, 'PDF produced by Microsoft Word ExportAsFixedFormat')
print(module.rasterize(sys.argv[1], sys.argv[3], 100, False, False))
