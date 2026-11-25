from pathlib import PurePosixPath

from django import forms
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from PIL import Image


IMAGE_FORMATS = {
    ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG",
    ".webp": "WEBP", ".gif": "GIF", ".ico": "ICO",
}
ATTACHMENT_EXTENSIONS = (".pdf", ".mp4", ".webm")


class MediaStorageUnavailable(OSError):
    pass


class ReadOnlyMediaStorage(FileSystemStorage):
    def save(self, name, content, max_length=None):
        raise MediaStorageUnavailable(
            "Persistent media storage is not configured. Set CLOUDINARY_URL or mount a persistent MEDIA_ROOT."
        )


def local_media_missing(file):
    """Check local files without issuing a remote request per media row."""
    storage = file.storage
    if isinstance(storage, FileSystemStorage):
        local = storage
    elif getattr(storage, "is_local_name", lambda name: False)(file.name):
        local = storage.local_storage
    else:
        return False
    if local.base_url.startswith(("http://", "https://", "//")):
        return False
    return not local.exists(file.name)


def upload_policy(kind="image"):
    extensions = {
        "image": tuple(IMAGE_FORMATS),
        "attachment": ATTACHMENT_EXTENSIONS,
        "all": (*IMAGE_FORMATS, *ATTACHMENT_EXTENSIONS),
    }[kind]
    formats = {
        "image": "JPEG, PNG, WebP, GIF, ICO",
        "attachment": "PDF, MP4, WebM",
        "all": "JPEG, PNG, WebP, GIF, ICO, PDF, MP4, WebM",
    }[kind]
    limit = settings.CMS_UPLOAD_MAX_BYTES
    hint = f"Форматы: {formats}. Максимум: {limit // (1024 * 1024)} МБ на файл."
    return {
        "accept": ",".join(extensions),
        "data-upload-limit": limit,
        "data-upload-hint": hint,
    }


def validate_upload(value, kind="image"):
    policy = upload_policy(kind)
    if value.size > policy["data-upload-limit"]:
        raise forms.ValidationError("Размер файла превышает допустимые 4 МБ", code="file_size")
    extension = PurePosixPath(value.name).suffix.lower()
    if extension not in policy["accept"].split(","):
        raise forms.ValidationError("Данный формат файла не поддерживается", code="file_format")
    expected_format = IMAGE_FORMATS.get(extension)
    if expected_format:
        try:
            with Image.open(value) as image:
                if image.format != expected_format:
                    raise forms.ValidationError("Содержимое изображения не соответствует расширению файла.")
                image.verify()
        except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
            raise forms.ValidationError("Файл повреждён или имеет недопустимые размеры.") from error
        finally:
            value.seek(0)
    else:
        try:
            header = value.read(4096)
        finally:
            value.seek(0)
        valid = {
            ".pdf": header.startswith(b"%PDF-"),
            ".mp4": header[4:8] == b"ftyp",
            ".webm": header.startswith(b"\x1a\x45\xdf\xa3") and b"\x42\x82\x84webm" in header,
        }[extension]
        if not valid:
            raise forms.ValidationError("Содержимое файла не соответствует расширению.", code="file_format")


def configure_image_uploads(form):
    for name, field in form.fields.items():
        if not isinstance(field, forms.ImageField):
            continue
        field.validators.append(validate_upload)
        field.error_messages["invalid_image"] = "Не удалось открыть изображение. Проверьте формат и целостность файла."
        field.widget.attrs.update(upload_policy())
        current = form.get_initial_for_field(field, name)
        if current and getattr(current, "url", None):
            field.widget.attrs["data-current-image"] = current.url
