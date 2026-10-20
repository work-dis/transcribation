from pathlib import Path
import mimetypes, shutil, tempfile
from .config import settings

SUPPORTED = {"audio/mpeg","audio/wav","audio/x-wav","audio/ogg","audio/mp4","audio/x-m4a","video/mp4","video/quicktime","video/webm","application/ogg"}
def validate_media(filename: str, mime_type: str | None, size_bytes: int) -> None:
    if size_bytes > settings.max_upload_size_mb * 1024 * 1024: raise ValueError("media exceeds configured upload limit")
    guessed = mime_type or mimetypes.guess_type(filename)[0] or ""
    if guessed not in SUPPORTED and Path(filename).suffix.lower() not in {".mp3",".wav",".m4a",".ogg",".mp4",".mov",".webm"}: raise ValueError("unsupported media type")
class LocalMediaStorage:
    def __init__(self, root: str = settings.temp_dir): self.root=Path(root)
    def conversation_dir(self, conversation_id: str) -> Path:
        p=self.root/conversation_id; p.mkdir(parents=True, exist_ok=True); return p
    def save(self, conversation_id: str, filename: str, source) -> Path:
        safe=Path(filename).name; target=self.conversation_dir(conversation_id)/safe
        with target.open("wb") as out: shutil.copyfileobj(source, out)
        return target
    def cleanup(self, conversation_id: str) -> None:
        p=self.root/conversation_id
        if p.exists(): shutil.rmtree(p)
