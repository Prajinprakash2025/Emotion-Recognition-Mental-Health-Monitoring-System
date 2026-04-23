from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('dashboard', '0003_connection'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivitySession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity_type', models.CharField(
                    choices=[
                        ('breathing', 'Breathing Exercise'),
                        ('game',      'Mood Game'),
                        ('music',     'Music Therapy'),
                        ('challenge', 'Positive Challenge'),
                    ],
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[('active', 'Active'), ('completed', 'Completed')],
                    default='active',
                    max_length=10,
                )),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('updated',   models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='activity_sessions',
                    to='auth.user',
                )),
            ],
            options={'ordering': ['-timestamp']},
        ),
    ]
