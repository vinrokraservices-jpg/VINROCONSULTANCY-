# Railway/Gunicorn wrapper.
# The requested main file keeps its exact name with hyphens.
import importlib.util
from pathlib import Path

target = Path(__file__).with_name("mpesa-webhook-server.py")
spec = importlib.util.spec_from_file_location("mpesa_webhook_server", target)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.app
