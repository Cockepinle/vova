from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch
from django.http import JsonResponse
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
from ..models import Product, ProductAttribute


class GroupMembershipChanged(Exception):
    pass


@management_required
def variant_group_list(request):
    groups = VariantGroup.objects.annotate(product_count=Count("products")).prefetch_related("attributes")
    return render(
        request,
        "store/management/variant_group_list.html",
        {"section": "variants", "groups": groups},
    )


@management_required
def variant_group_form(request, group_id=None):
    embedded = request.headers.get("X-Variant-Dialog") == "1"
    group = get_object_or_404(VariantGroup, pk=group_id) if group_id else None
    form = VariantGroupForm(
        request.POST if request.method == "POST" else None,
        instance=group,
    )
    parameter_forms = VariantParameterFormSet(
        request.POST if request.method == "POST" else None,
        prefix="parameters",
    )

    if request.method == "POST" and all((form.is_valid(), parameter_forms.is_valid())):
        is_new = group is None
        try:
            with transaction.atomic():
                if not is_new:
                    get_object_or_404(VariantGroup.objects.select_for_update(no_key=True), pk=group.pk)
                product_ids = [product.pk for product in form.cleaned_data["products"]]
                products = list(Product.objects.filter(pk__in=product_ids).order_by("pk").select_for_update())
                permitted_groups = {None, group.pk if group else None}
                if len(products) != len(product_ids) or any(product.variant_group_id not in permitted_groups for product in products):
                    raise GroupMembershipChanged
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
                            "choices": list(dict.fromkeys(
                                item.strip()
                                for item in data["choices_text"].splitlines()
                                if item.strip()
                            )),
                        },
                    )
                    if parameter.is_visible:
                        selected_attributes.append(parameter)
                group.attributes.set(selected_attributes)
                members = {product.pk for product in products}
                removed = set(group.products.exclude(pk__in=members).values_list("pk", flat=True))
                group.products.set(products)
                log_change(
                    request,
                    group,
                    ADDITION if is_new else CHANGE,
                    "Сохранена группа модификаций",
                )
            if embedded:
                return JsonResponse({
                    "id": group.pk, "name": group.name, "created": is_new,
                    "members": sorted(members), "removed": sorted(removed),
                })
            messages.success(request, "Группа модификаций сохранена.")
            return redirect("management_variant_group_edit", group_id=group.pk)

        except GroupMembershipChanged:
            form.add_error("products", "Состав групп изменился. Откройте форму повторно и проверьте выбранные товары.")
        except IntegrityError:
            form.add_error(None, "Не удалось сохранить группу. Проверьте, свободно ли её название.")

    linked_products = []
    if group:
        values = ProductAttribute.objects.filter(attribute__variant_groups=group).select_related("attribute")
        linked_products = group.products.order_by("name", "pk").prefetch_related(
            Prefetch("attributes", queryset=values, to_attr="variant_values")
        )
    return render(
        request,
        "store/management/variant_group_fields.html" if embedded else "store/management/variant_group_form.html",
        {
            "section": "variants",
            "group": group,
            "embedded": embedded,
            "form": form,
            "parameter_forms": parameter_forms,
            "linked_products": linked_products,
        },
        status=422 if embedded and request.method == "POST" else 200,
    )


@management_required
@require_POST
@transaction.atomic
def variant_group_delete(request, group_id):
    group = get_object_or_404(VariantGroup.objects.select_for_update(), pk=group_id)
    log_change(request, group, DELETION, "Удалена группа модификаций")
    group.delete()
    messages.success(
        request,
        "Группа удалена. Товары и их характеристики сохранены.",
    )
    return redirect("management_variant_groups")
