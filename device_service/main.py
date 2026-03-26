from bootstrap import resolve_directory
from device_service.app import create_app

app = create_app(str(resolve_directory(None)))
