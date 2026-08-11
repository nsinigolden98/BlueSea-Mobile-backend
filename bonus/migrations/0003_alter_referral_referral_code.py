from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("bonus", "0002_referral_count"),
    ]

    operations = [
        migrations.AlterField(
            model_name="referral",
            name="referral_code",
            field=models.CharField(max_length=20),
        ),
    ]
