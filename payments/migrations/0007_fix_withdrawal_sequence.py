from django.db import connection, migrations


def fix_withdrawal_sequence(apps, schema_editor):
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as c:
        c.execute(
            "ALTER TABLE payments_withdrawal "
            "ALTER COLUMN id TYPE bigint USING id::text::bigint"
        )
        c.execute(
            "CREATE SEQUENCE IF NOT EXISTS payments_withdrawal_id_seq "
            "OWNED BY payments_withdrawal.id"
        )
        c.execute(
            "ALTER TABLE payments_withdrawal "
            "ALTER COLUMN id SET DEFAULT nextval('payments_withdrawal_id_seq')"
        )
        c.execute(
            "SELECT setval('payments_withdrawal_id_seq', "
            "GREATEST(COALESCE(MAX(id),0),1), MAX(id) IS NOT NULL) "
            "FROM payments_withdrawal"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0006_add_user_fk_to_payment_models"),
    ]

    operations = [
        migrations.RunPython(fix_withdrawal_sequence, migrations.RunPython.noop),
    ]
