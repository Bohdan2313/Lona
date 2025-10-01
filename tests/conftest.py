import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Lightweight stubs for heavy optional dependencies used during import time
if "numpy" not in sys.modules:  # pragma: no cover
    numpy_stub = types.ModuleType("numpy")
    numpy_stub.ndarray = list
    numpy_stub.integer = int
    numpy_stub.floating = float
    numpy_stub.array = lambda value=None: value
    sys.modules["numpy"] = numpy_stub

if "pandas" not in sys.modules:  # pragma: no cover
    pandas_stub = types.ModuleType("pandas")

    class _Series(list):
        def tolist(self):
            return list(self)

    pandas_stub.Series = _Series
    pandas_stub.Timestamp = str
    sys.modules["pandas"] = pandas_stub
