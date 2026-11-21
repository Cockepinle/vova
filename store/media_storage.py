from pathlib import PurePosixPath
from uuid import uuid4

from cloudinary.exceptions import Error
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile


class StoreCloudinaryStorage(MediaCloudinaryStorage):
    video_extensions = {".mp4", ".webm", ".mov"}
    raw_extensions = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt", ".zip"}
    local_storage = FileSystemStorage()

    def is_local_name(self, name):
        return not name.startswith(self._get_prefix().strip("/") + "/")

    def url(self, name):
        if self.is_local_name(name):
            return self.local_storage.url(name)
        return super().url(name)

    def _open(self, name, mode="rb"):
        if self.is_local_name(name):
            return self.local_storage.open(name, mode)
        return super()._open(name, mode)

    def exists(self, name):
        if self.is_local_name(name):
            return self.local_storage.exists(name)
        return super().exists(name)

    def size(self, name):
        if self.is_local_name(name):
            return self.local_storage.size(name)
        return super().size(name)

    def _get_resource_type(self, name):
        extension = PurePosixPath(name).suffix.lower()
        if extension in self.video_extensions:
            return "video"
        if extension in self.raw_extensions:
            return "raw"
        return "image"

    def get_available_name(self, name, max_length=None):
        # The upstream backend truncates the entire path, including its extension.
        path = PurePosixPath(self._normalise_name(name))
        candidate = str(path.with_name(f"{uuid4().hex}{path.suffix.lower()}"))
        if max_length and len(self._prepend_prefix(candidate)) > max_length:
            raise OSError("Cloudinary media path exceeds the length of the file field.")
        return candidate

    def _save(self, name, content):
        name = self._prepend_prefix(self._normalise_name(name))
        try:
            result = self._upload(name, UploadedFile(content, name))
        except Error as error:
            raise OSError("Cloudinary could not store the file.") from error
        public_id = result["public_id"]
        if self._get_resource_type(name) == "raw":
            return public_id
        extension = result.get("format") or PurePosixPath(name).suffix.lstrip(".")
        return f"{public_id}.{extension}" if extension else public_id

    def delete(self, name):
        if self.is_local_name(name):
            return self.local_storage.delete(name)
        resource_type = self._get_resource_type(name)
        if resource_type == "raw":
            return super().delete(name)
        from cloudinary.uploader import destroy
        extension = PurePosixPath(name).suffix
        public_id = name.removesuffix(extension) if extension else name
        return destroy(public_id, invalidate=True, resource_type=resource_type)["result"] == "ok"
