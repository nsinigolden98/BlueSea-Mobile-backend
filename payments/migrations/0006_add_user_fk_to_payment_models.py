from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('payments', '0005_alter_airteldatatopup_plan_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='airtimetopup',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='airtime_topups', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='mtndatatopup',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='mtn_data_topups', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='airteldatatopup',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='airtel_data_topups', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='glodatatopup',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='glo_data_topups', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='etisalatdatatopup',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='etisalat_data_topups', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dstvpayment',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='dstv_payments', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='gotvpayment',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='gotv_payments', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='startimespayment',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='startimes_payments', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='showmaxpayment',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='showmax_payments', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='electricitypayment',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='electricity_payments', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='waecregitration',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='waec_registrations', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='waecresultchecker',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='waec_result_checks', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='jambregistration',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='jamb_registrations', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='airtime2cash',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='airtime2cash_records', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='electricitypaymentcustomers',
            name='user',
            field=models.ForeignKey(default=1, on_delete=models.CASCADE, related_name='electricity_customer_lookups', to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
    ]
