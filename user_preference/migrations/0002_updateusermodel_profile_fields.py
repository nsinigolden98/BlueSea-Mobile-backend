from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("user_preference", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="updateusermodel",
            name="date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="updateusermodel",
            name="country",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="updateusermodel",
            name="state",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="updateusermodel",
            name="city",
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name="updateusermodel",
            name="street_address",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="updateusermodel",
            name="landmark",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="updateusermodel",
            name="postal_code",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
    ]
