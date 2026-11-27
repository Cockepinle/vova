from copy import copy
from html import unescape

from django import forms
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.cache import add_never_cache_headers
from django.utils.html import strip_tags

from ..legacy_documents import legacy_document
from ..models import PageContent, SiteSettings
from ..seo import metadata
from ..services.site import apply_common_context
from .common import CHANGE, log_change, messages
from .content import _BuilderHTMLSanitizer

LEGAL_KEYS = ("privacy", "offer")
LEGAL_PERMISSION = "store.change_pagecontent"
EDIT_FIELDS = ("title", "h1", "is_visible", "seo_title", "meta_description", "document_html")


class LegalHTMLSanitizer(_BuilderHTMLSanitizer):
    allowed_tags = _BuilderHTMLSanitizer.allowed_tags | {
        "h5", "h6", "table", "caption", "thead", "tbody", "tfoot", "tr", "td", "th",
    }
    void_tags = {"br", "embed", "input", "link", "meta"}
    blocked_tags = (_BuilderHTMLSanitizer.blocked_tags - void_tags) | {"head", "template", "textarea", "button", "select"}

    def safe_attributes(self, tag, attributes):
        result = super().safe_attributes(tag, attributes)
        styles = {}
        for declaration in (attributes.get("style") or "").split(";"):
            name, _, value = declaration.partition(":")
            styles[name.strip().lower()] = value.strip().lower()
        safe_styles = {}
        if tag in {"p", "div", "h2", "h3", "h4", "h5", "h6", "li", "td", "th"}:
            alignment = styles.get("text-align", attributes.get("align"))
            if alignment in {"left", "right", "center", "justify"}:
                safe_styles["text-align"] = alignment
        if tag == "span":
            for name, values in {"font-weight": {"bold", "600", "700", "800", "900"},
                                 "font-style": {"italic"}, "text-decoration": {"underline"},
                                 "text-decoration-line": {"underline"}}.items():
                if styles.get(name) in values:
                    safe_styles[name] = styles[name]
        if safe_styles:
            result["style"] = "; ".join(f"{name}: {value}" for name, value in safe_styles.items())
        if (tag, attributes.get("class")) in {("p", "document-lead"), ("div", "document-section"), ("div", "document-note")}:
            result["class"] = attributes["class"]
        numeric = {"ol": ("start",), "li": ("value",), "td": ("colspan", "rowspan"),
                   "th": ("colspan", "rowspan")}
        for name in numeric.get(tag, ()):
            value = attributes.get(name) or ""
            if value.isascii() and value.isdecimal() and 1 <= len(value) <= 4 and int(value) > 0:
                result[name] = value
        if tag == "ol" and attributes.get("type") in {"1", "a", "A", "i", "I"}:
            result["type"] = attributes["type"]
        return result


def sanitize_document(source):
    parser = LegalHTMLSanitizer()
    parser.feed(source)
    parser.close()
    return parser.get_html()


class LegalDocumentForm(forms.ModelForm):
    footer_label = forms.CharField(label="Название ссылки в футере", max_length=120)
    document_html = forms.CharField(
        label="Содержимое документа", max_length=500000,
        widget=forms.Textarea(attrs={"rows": 18, "data-legal-source": ""}),
    )

    class Meta:
        model = PageContent
        fields = EDIT_FIELDS
        labels = {"title": "Название страницы", "h1": "Отдельный H1 (необязательно)",
                  "is_visible": "Опубликован", "seo_title": "SEO title"}
        widgets = {"meta_description": forms.Textarea(attrs={"rows": 3})}

    def clean_document_html(self):
        cleaned = sanitize_document(self.cleaned_data["document_html"])
        if not unescape(strip_tags(cleaned)).strip():
            raise forms.ValidationError("Введите текст документа.")
        return cleaned


def render_document(request, slug, page=None, *, preview=False, footer_label=None):
    config = SiteSettings.get_solo()
    context = {
        "document": legacy_document(slug, config),
        "formatted_document": sanitize_document(page.document_html) if page else "",
        "show_footer_cta": False,
    }
    if page:
        context["current_page"] = page
        context["builder_structure"] = page.published_structure
        context["builder_design"] = page.published_design
    if preview:
        config = copy(config)
        setattr(config, f"footer_{slug}_label", footer_label)
        context.update({
            "site_settings": config,
            "document_preview": True,
            "seo": {**metadata(request, config, {slug: page}, page_key=slug), "noindex": True},
        })
    apply_common_context(request, context)
    response = render(request, "store/document.html", context)
    if preview:
        add_never_cache_headers(response)
        response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def list_documents(request):
    if not request.user.has_perm(LEGAL_PERMISSION):
        raise PermissionDenied
    records = PageContent.objects.filter(page__in=LEGAL_KEYS, is_custom=False).in_bulk(field_name="page")
    return render(request, "store/management/legal_document_list.html", {
        "section": "pages", "content_section": "legal",
        "documents": [records[key] for key in LEGAL_KEYS if key in records],
    })


def edit_document(request, page):
    if not request.user.has_perm(LEGAL_PERMISSION):
        raise PermissionDenied
    config = SiteSettings.get_solo()
    label_field = f"footer_{page.page}_label"
    initial = {
        "footer_label": getattr(config, label_field),
        "title": page.title or page.get_page_display(),
        "document_html": page.document_html or render_to_string("store/partials/document_text.html", {
            "document": legacy_document(page.page, config), "current_page": page,
        }).strip(),
    }
    form = LegalDocumentForm(request.POST if request.method == "POST" else None, instance=page, initial=initial)
    if request.method == "POST" and form.is_valid():
        if "preview_document" in request.POST:
            return render_document(request, page.page, form.save(commit=False), preview=True,
                                   footer_label=form.cleaned_data["footer_label"])
        with transaction.atomic():
            page.save(update_fields=[*EDIT_FIELDS, "updated_at"])
            SiteSettings.objects.filter(pk=config.pk).update(**{label_field: form.cleaned_data["footer_label"]})
            log_change(request, page, CHANGE, "Юридический документ сохранён через CMS")
        messages.success(request, "Документ сохранён.")
        if request.POST.get("action") == "continue":
            return redirect("management_page_edit", page_id=page.pk)
        return redirect(reverse("management_pages") + "?section=legal")
    response = render(request, "store/management/legal_document_form.html", {
        "section": "pages", "content_section": "legal", "document": page, "form": form,
    })
    add_never_cache_headers(response)
    return response
