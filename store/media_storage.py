from pathlib import PurePosixPath
from uuid import uuid4

from cloudinary import CloudinaryResource, uploader
from cloudinary.exceptions import AuthorizationRequired, BadRequest, Error, NotAllowed, RateLimited
from cloudinary_storage.storage import MediaCloudinaryStorage
from django.core.files.storage import FileSystemStorage
from urllib3.exceptions import HTTPError

from .uploads import MediaProviderError


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

    def _get_url(self, name):
        resource_type = self._get_resource_type(name)
        return CloudinaryResource(self._prepend_prefix(name), default_resource_type=resource_type).build_url(secure=True)

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
            resource_type = self._get_resource_type(name)
            extension = PurePosixPath(name).suffix
            public_id = name if resource_type == "raw" else name.removesuffix(extension)
            content.seek(0)
            result = uploader.upload(
                content, filename=PurePosixPath(name).name, public_id=public_id,
                resource_type=resource_type, tags=self.TAG, overwrite=False, timeout=30,
            )
        except (AuthorizationRequired, NotAllowed, ValueError) as error:
            raise MediaProviderError("Cloudinary отклонил авторизацию. Проверьте CLOUDINARY_URL и права ключа.") from error
        except RateLimited as error:
            raise MediaProviderError("Cloudinary ограничил частоту загрузок. Повторите попытку позже.") from error
        except BadRequest as error:
            raise MediaProviderError("Cloudinary отклонил файл или параметры загрузки. Подробности в журнале сервера.") from error
        except (Error, HTTPError, TimeoutError) as error:
            raise MediaProviderError("Cloudinary не подтвердил запись. Проверьте доступность хранилища и повторите попытку.") from error
        public_id = result.get("public_id")
        if not isinstance(public_id, str) or not public_id.startswith(self._get_prefix().strip("/") + "/"):
            raise MediaProviderError("Cloudinary вернул неожиданный идентификатор файла. Проверьте настройки хранилища.")
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
