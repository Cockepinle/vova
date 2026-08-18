from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("store", "0005_image_uploads"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="product",
            name="badge",
        ),
        migrations.RemoveField(
            model_name="product",
            name="is_active",
        ),
    ]
