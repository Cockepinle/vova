from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("store", "0019_brand_footer_links")]

    operations = [migrations.RemoveField(model_name="pagecontent", name="image_alt")]
