from django.db import migrations, models


def enable_table_columns(apps, schema_editor):
    AttributeDefinition = apps.get_model("store", "AttributeDefinition")
    AttributeDefinition.objects.update(show_in_table=True)


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0006_simplify_product_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="attributedefinition",
            name="show_in_table",
            field=models.BooleanField(default=True, verbose_name="Показывать в таблице"),
        ),
        migrations.RunPython(enable_table_columns, migrations.RunPython.noop),
    ]
