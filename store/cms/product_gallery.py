import json
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError

from ..models import ProductImage, SiteMedia


def gallery_rows(product):
    rows = {}
    if not product:
        return rows

    for image in product.images.select_related("media"):
        if image.display_url and (not image.media_id or image.media.is_image):
            rows[f"link:{image.pk}"] = {
                "url": image.display_url, "alt": image.alt, "mediaId": image.media_id,
                "primary": image.is_primary, "link": image,
            }
    if product.image:
        rows["cover:file"] = {"url": product.image.url, "alt": product.name, "cover_file": product.image.name}
    if product.image_url:
        rows["cover:url"] = {"url": product.image_url, "alt": product.name, "external_url": product.image_url}
    linked_media = {row.get("mediaId") for row in rows.values()}
    for media in product.media.filter(media_type=SiteMedia.TYPE_IMAGE):
        if media.pk not in linked_media and media.file and media.is_image:
            rows[f"media:{media.pk}"] = media_row(media)
    return rows


def media_row(media):
    return {"url": media.file.url, "alt": media.alt, "title": media.title, "mediaId": media.pk}


def public_gallery(rows, primary):
    return [
        {**{name: row[name] for name in ("url", "alt", "title", "mediaId") if name in row},
         "key": key, "primary": key == primary}
        for key, row in rows.items()
    ]


def initial_gallery(rows):
    primary = next((key for key, row in rows.items() if row.get("primary")), None)
    if primary is None:
        primary = next((key for key in ("cover:file", "cover:url") if key in rows), next(iter(rows), None))
    return public_gallery(rows, primary)


def parse_gallery(value, current):
    try:
        data = json.loads(value)
        entries = data["items"]
        primary = data["primary"]
        if not isinstance(entries, list):
            raise ValueError
        keys = [entry["key"] for entry in entries]
        if not all(isinstance(key, str) and len(key) <= 64 for key in keys):
            raise ValueError
        if len(set(keys)) != len(keys) or (primary not in keys if keys else primary is not None):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValidationError("Не удалось прочитать порядок фотографий. Обновите страницу и повторите выбор.")

    missing = [key[6:] for key in keys if key not in current and key.startswith("media:")]
    if not all(value.isascii() and value.isdecimal() and 0 < len(value) <= 18 for value in missing):
        raise ValidationError("Медиатека вернула некорректное изображение.")
    media_by_key = {
        f"media:{media.pk}": media_row(media)
        for media in SiteMedia.objects.filter(pk__in=missing, media_type=SiteMedia.TYPE_IMAGE)
        if media.file and media.is_image
    }
    rows = {}
    seen_media = set()
    for key, entry in zip(keys, entries):
        row = current.get(key) or media_by_key.get(key)
        if row is None and key.startswith("url:"):
            url = entry.get("url")
            try:
                parsed = urlsplit(url) if isinstance(url, str) and len(url) <= 200 else None
            except ValueError:
                parsed = None
            if not parsed or parsed.scheme not in {"http", "https"} or not parsed.hostname or "\\" in url or any(ord(char) < 32 for char in url):
                raise ValidationError("Укажите полный адрес фотографии http:// или https://.")
            row = {"url": url, "external_url": url}
        if row is None:
            raise ValidationError("Одна из фотографий больше недоступна. Обновите страницу и повторите выбор.")
        alt = entry.get("alt", "")
        if not isinstance(alt, str) or len(alt) > 180:
            raise ValidationError("Описание фотографии должно содержать не более 180 символов.")
        media_id = row.get("mediaId")
        if media_id and media_id in seen_media and key not in current:
            raise ValidationError("Эта фотография уже есть в галерее товара.")
        if media_id:
            seen_media.add(media_id)
        rows[key] = {**row, "alt": alt.strip()}
    return rows, primary


def save_gallery(product, current, rows, primary):
    removed_ids = [row["link"].pk for key, row in current.items() if key not in rows and "link" in row]
    if removed_ids:
        product.images.filter(pk__in=removed_ids).delete()

    product.images.filter(is_primary=True).update(is_primary=False)
    images = []
    selected_id = None
    for index, (key, row) in enumerate(rows.items()):
        image = row.get("link")
        if image:
            image.alt = row["alt"]
            image.sort_order = index
            images.append(image)
        else:
            image = ProductImage.objects.create(
                product=product, media_id=row.get("mediaId"), image=row.get("cover_file", ""),
                image_url=row.get("external_url", ""), alt=row["alt"], sort_order=index,
            )
        if key == primary:
            selected_id = image.pk
    if images:
        ProductImage.objects.bulk_update(images, ["alt", "sort_order"])
    if selected_id:
        product.images.filter(pk=selected_id).update(is_primary=True)
    if product.image or product.image_url:
        product.image, product.image_url = "", ""
        product.save(update_fields=["image", "image_url"])
    image_ids = [media.pk for media in product.media.filter(media_type=SiteMedia.TYPE_IMAGE) if media.is_image]
    if image_ids:
        product.media.remove(*image_ids)
