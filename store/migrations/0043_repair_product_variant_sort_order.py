from django.db import migrations, models


def restore_missing_column(apps, schema_editor):
    product = apps.get_model("store", "Product")
    field = product._meta.get_field("variant_sort_order")
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(cursor, product._meta.db_table)
    if field.column not in {column.name for column in columns}:
        schema_editor.add_field(product, field)


class Migration(migrations.Migration):
    dependencies = [("store", "0042_product_variant_sort_order")]

    operations = [
        # The prior migration already owns this column in Django's state.
        migrations.RunPython(restore_missing_column, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="variant_sort_order",
            field=models.PositiveIntegerField(
                "Порядок в группе модификаций", default=0, db_default=0,
            ),
        ),
    ]
