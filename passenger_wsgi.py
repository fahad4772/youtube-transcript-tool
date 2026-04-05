from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

spec = spec_from_file_location("transcribe", BASE_DIR / "transcribe.py")
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

application = module.app
