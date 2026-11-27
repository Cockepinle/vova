from django.db import migrations
from django.template.loader import render_to_string

from store.legacy_documents import legacy_document


def seed_legal_documents(apps, schema_editor):
    alias = schema_editor.connection.alias
    pages = apps.get_model("store", "PageContent").objects.using(alias)
    config = apps.get_model("store", "SiteSettings").objects.using(alias).filter(pk=1).first()
    for slug in ("privacy", "offer"):
        page, _ = pages.get_or_create(page=slug)
        if not page.is_custom and not page.document_html:
            body = render_to_string("store/partials/document_text.html", {
                "document": legacy_document(slug, config), "current_page": page,
            }).strip()
            pages.filter(pk=page.pk, document_html="").update(document_html=body)


class Migration(migrations.Migration):
    dependencies = [("store", "0047_pagecontent_document_html_promotion_conditions_and_more")]
    operations = [migrations.RunPython(seed_legal_documents, migrations.RunPython.noop)]
