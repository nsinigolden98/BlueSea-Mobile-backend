from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "market_place",
            "0004_alter_issuedticket_options_alter_tickettype_options_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="eventinfo",
            name="quantity",
            field=models.IntegerField(
                blank=True, help_text="Total quantity for free events", null=True
            ),
        ),
    ]
