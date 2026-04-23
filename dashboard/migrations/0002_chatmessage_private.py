from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('dashboard', '0001_initial'),
    ]

    operations = [
        # Rename old related_name on sender to match new model
        migrations.AlterField(
            model_name='chatmessage',
            name='sender',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='sent_messages',
                to='auth.user',
            ),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='receiver',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='received_messages',
                to='auth.user',
            ),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='is_private',
            field=models.BooleanField(default=False),
        ),
    ]
