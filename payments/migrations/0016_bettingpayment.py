from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0015_withdrawal_provider'),
    ]

    operations = [
        migrations.CreateModel(
            name='BettingPayment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(max_length=50)),
                ('customer_id', models.CharField(max_length=50)),
                ('amount', models.IntegerField()),
                ('phone_number', models.CharField(max_length=11)),
                ('request_id', models.CharField(blank=True, max_length=50, null=True, unique=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('delivered', 'Delivered'), ('failed', 'Failed'), ('reversed', 'Reversed')], db_index=True, default='pending', max_length=20)),
                ('vtpass_transaction_id', models.CharField(blank=True, max_length=100, null=True)),
                ('vtpass_response', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='betting_payments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
