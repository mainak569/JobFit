from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("resumes", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="resume",
            old_name="r2_key",
            new_name="storage_key",
        ),
    ]
