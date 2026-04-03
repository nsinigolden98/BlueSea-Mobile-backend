from django.db import migrations, models
import group_payment.models


class Migration(migrations.Migration):
    dependencies = [
        ("group_payment", "0005_update_group_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="group",
            name="join_code",
            field=models.CharField(
                default=group_payment.models.generate_join_code,
                max_length=10,
                unique=True,
            ),
        ),
    ]
