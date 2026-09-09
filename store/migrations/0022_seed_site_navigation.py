from django.db import migrations


def seed_navigation(apps, schema_editor):
    Settings = apps.get_model('store', 'SiteSettings')
    Link = apps.get_model('store', 'SiteLink')
    Page = apps.get_model('store', 'PageContent')
    settings, _ = Settings.objects.get_or_create(pk=1)
    for index, key in enumerate(['home', 'catalog', 'team', 'contacts']):
        for location in ['header', 'footer']:
            Link.objects.create(settings=settings, location=location,
                label=getattr(settings, f'nav_{key}_label'),
                url=getattr(settings, f'nav_{key}_url'), sort_order=index)
    for key in ['home', 'catalog', 'team', 'contacts', 'privacy', 'offer']:
        Page.objects.get_or_create(page=key)


class Migration(migrations.Migration):
    dependencies = [('store', '0021_editable_site_content')]
    operations = [migrations.RunPython(seed_navigation, migrations.RunPython.noop)]
