from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='bio',
            field=models.TextField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='support_preference',
            field=models.CharField(
                blank=True, default='',
                choices=[('talk', 'Open to Talk'), ('listen', 'Prefer Listening'),
                         ('need', 'Needs Support'), ('', 'Not specified')],
                max_length=10,
            ),
        ),
    ]
