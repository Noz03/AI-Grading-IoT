"""Validated, private local storage for submission images."""

import io
import os
import tempfile
import warnings
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from ai_grading_iot.core.config import get_settings


MAX_BYTES = 10 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 40_000_000
FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"),
           "WEBP": ("webp", "image/webp")}


class ImageStorageError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(message)


class ImageStorageService:
    def __init__(self, root: str | Path | None = None):
        configured = Path(root if root is not None else get_settings().UPLOAD_DIR)
        # Relative settings are anchored at the project root, independent of process cwd.
        project_root = Path(__file__).resolve().parents[3]
        self.root = (configured if configured.is_absolute() else project_root / configured).resolve()

    def reference(self, submission_id: UUID, image_id: UUID, extension: str) -> str:
        if extension not in {item[0] for item in FORMATS.values()}:
            raise ImageStorageError(404, "Image not found")
        return f"submissions/{submission_id}/{image_id}.{extension}"

    def path(self, reference: str) -> Path:
        parts = Path(reference).parts
        if len(parts) != 3 or parts[0] != "submissions":
            raise ImageStorageError(404, "Image not found")
        try:
            UUID(parts[1])
            image_id, extension = parts[2].rsplit(".", 1)
            UUID(image_id)
        except (ValueError, IndexError) as exc:
            raise ImageStorageError(404, "Image not found") from exc
        if extension not in {item[0] for item in FORMATS.values()}:
            raise ImageStorageError(404, "Image not found")
        path = self.root.joinpath(*parts)
        if not path.resolve().is_relative_to(self.root) or path.is_symlink():
            raise ImageStorageError(404, "Image not found")
        return path

    def validate(self, upload: UploadFile) -> tuple[bytes, str, str]:
        payload = upload.file.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise ImageStorageError(413, "Image exceeds 10 MiB")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(payload)) as image:
                    image.verify()
                with Image.open(io.BytesIO(payload)) as image:
                    if image.format not in FORMATS:
                        raise ImageStorageError(415, "Unsupported image format")
                    extension, media_type = FORMATS[image.format]
                    supplied = Path(upload.filename or "").suffix.lower().lstrip(".")
                    if supplied and supplied != extension and not (extension == "jpg" and supplied == "jpeg"):
                        raise ImageStorageError(415, "Image extension does not match content")
                    image.load()
                    oriented = ImageOps.exif_transpose(image)
                    normalized = oriented.convert("RGB") if image.format == "JPEG" else oriented.copy()
                    output = io.BytesIO()
                    normalized.save(output, format=image.format, quality=95)
                    return output.getvalue(), extension, media_type
        except ImageStorageError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
                Image.DecompressionBombWarning) as exc:
            raise ImageStorageError(415, "Invalid image") from exc

    def store(self, reference: str, payload: bytes) -> None:
        path = self.path(reference)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".upload-", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(payload)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def read(self, reference: str) -> bytes:
        try:
            return self.path(reference).read_bytes()
        except FileNotFoundError as exc:
            raise ImageStorageError(404, "Image not found") from exc

    def remove(self, reference: str) -> None:
        self.path(reference).unlink(missing_ok=True)
