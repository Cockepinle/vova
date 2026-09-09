from django.db import migrations, models


def move_page_settings(apps, schema_editor):
    SiteSettings = apps.get_model("store", "SiteSettings")
    PageContent = apps.get_model("store", "PageContent")
    settings = SiteSettings.objects.order_by("pk").first()
    if not settings:
        return

    values = {
        "home": {"title": settings.home_hero_title, "h1": settings.home_hero_title, "subtitle": settings.home_hero_subtitle, "hero_label": settings.home_hero_label},
        "catalog": {"title": settings.catalog_title, "h1": settings.catalog_title, "subtitle": settings.catalog_subtitle},
        "team": {"title": settings.team_hero_title, "h1": settings.team_hero_title, "subtitle": settings.team_hero_subtitle, "hero_label": settings.team_hero_label},
        "contacts": {"title": settings.contacts_hero_title, "h1": settings.contacts_hero_title, "hero_label": settings.contacts_hero_label, "content_title": settings.contacts_form_title, "b2b_title": settings.contacts_b2b_title, "content_subtitle": settings.contacts_b2b_subtitle, "content_text": settings.contacts_b2b_text},
    }
    for page_name, defaults in values.items():
        page, _ = PageContent.objects.get_or_create(page=page_name)
        changed = False
        for key, value in defaults.items():
            if not getattr(page, key, "") and value:
                setattr(page, key, value)
                changed = True
        if page_name == "home" and getattr(settings, "hero_image", None) and not page.hero_image:
            page.hero_image = settings.hero_image
            page.hero_image_alt = settings.hero_image_alt
            changed = True
        if changed:
            page.save()


class Migration(migrations.Migration):
    dependencies = [("store", "0017_cms_media_seo")]

    operations = [
        migrations.AddField(model_name="pagecontent", name="hero_image", field=models.ImageField(blank=True, upload_to="pages/", verbose_name="Изображение главного блока")),
        migrations.AddField(model_name="pagecontent", name="hero_image_alt", field=models.CharField(blank=True, max_length=180, verbose_name="Alt изображения главного блока")),
        migrations.AddField(model_name="pagecontent", name="content_title", field=models.CharField(blank=True, max_length=220, verbose_name="Заголовок дополнительного блока")),
        migrations.AddField(model_name="pagecontent", name="content_subtitle", field=models.CharField(blank=True, max_length=220, verbose_name="Подзаголовок дополнительного блока")),
        migrations.AddField(model_name="pagecontent", name="content_text", field=models.TextField(blank=True, verbose_name="Текст дополнительного блока")),
        migrations.AddField(model_name="pagecontent", name="b2b_title", field=models.CharField(blank=True, max_length=220, verbose_name="Заголовок B2B-блока")),
        migrations.RunPython(move_page_settings, migrations.RunPython.noop),
        migrations.RemoveField(model_name="sitesettings", name="hero_image"),
        migrations.RemoveField(model_name="sitesettings", name="hero_image_alt"),
    ]
