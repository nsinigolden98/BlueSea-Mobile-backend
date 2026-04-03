from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("group_payment", "0004_remove_group_status_group_active"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="group",
            name="join_code",
        ),
        migrations.AddField(
            model_name="group",
            name="current_amount",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="group",
            name="deadline",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="group",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("partial", "Partially Paid"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("canceled", "Canceled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="groupmember",
            name="locked_amount",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="groupmember",
            name="paid_amount",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="groupmember",
            name="payment_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("locked", "Amount Locked"),
                    ("paid", "Paid"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
