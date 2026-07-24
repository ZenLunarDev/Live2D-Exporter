from .extension import Live2DExporterExtension
import os
import datetime

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_PATH = os.path.join(_SCRIPT_DIR, "live2d-prep.log")

try:
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Live2D Prep plugin loaded from: {_SCRIPT_DIR}\n")
except Exception:
    pass

Krita.instance().addExtension(Live2DExporterExtension(Krita.instance()))  # type: ignore
