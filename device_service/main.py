import os

from bootstrap import resolve_directory
from device_service.app import create_app

media_directory = os.getenv("MP3_MEDIA_DIR")
app = create_app(str(resolve_directory(media_directory)))
