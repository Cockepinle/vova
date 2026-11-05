from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .common import (
    AttributeDefinition,
    VariantGroup,
    log_change,
    management_required,
    messages,
)
from ..cms_forms import VariantGroupForm, VariantParameterFormSet


@management_required
def variant_group_list(request):
    groups = VariantGroup.objects.prefetch_related("products").all()
    return render(
        request,
        "store/management/variant_group_list.html",
        {"section": "variants", "groups": groups},
    )


@management_required
def variant_group_form(request, group_id=None):
    group = get_object_or_404(VariantGroup, pk=group_id) if group_id else None
    form = VariantGroupForm(
        request.POST or None,
        instance=group,
    )
    parameter_forms = VariantParameterFormSet(
        request.POST or None,
        prefix="parameters",
    )

    if request.method == "POST" and form.is_valid() and parameter_forms.is_valid():
        is_new = group is None
        with transaction.atomic():
            group = form.save()
            selected_attributes = list(form.cleaned_data["attributes"])
            for parameter_form in parameter_forms:
                data = parameter_form.cleaned_data
                if not data or data.get("DELETE") or not data.get("name"):
                    continue
                parameter, _ = AttributeDefinition.objects.get_or_create(
                    name=data["name"],
                    defaults={
                        "value_type": data["value_type"]
                        or AttributeDefinition.TYPE_TEXT,
                        "unit": data["unit"],
                        "choices": [
                            item.strip()
                            for item in data["choices_text"].splitlines()
                            if item.strip()
                        ],
                    },
                )
                if parameter.is_visible:
                    selected_attributes.append(parameter)
            group.attributes.set(selected_attributes)
            group.products.set(form.cleaned_data["products"])
            log_change(
                request,
                group,
                ADDITION if is_new else CHANGE,
                "Сохранена группа модификаций",
            )
        messages.success(request, "Группа модификаций сохранена.")
        return redirect("management_variant_group_edit", group_id=group.pk)

    return render(
        request,
        "store/management/variant_group_form.html",
        {
            "section": "variants",
            "group": group,
            "form": form,
            "parameter_forms": parameter_forms,
        },
    )


@management_required
@require_POST
def variant_group_delete(request, group_id):
    group = get_object_or_404(VariantGroup, pk=group_id)
    log_change(request, group, DELETION, "Удалена группа модификаций")
    group.products.update(variant_group=None)
    group.delete()
    messages.success(
        request,
        "Группа удалена. Товары и их характеристики сохранены.",
    )
    return redirect("management_variant_groups")
