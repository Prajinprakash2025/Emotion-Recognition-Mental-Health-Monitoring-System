from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say'),
    ]
    SUPPORT_CHOICES = [
        ('talk',   'Open to Talk'),
        ('listen', 'Prefer Listening'),
        ('need',   'Needs Support'),
        ('',       'Not specified'),
    ]

    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    gender     = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    age        = models.PositiveSmallIntegerField(null=True, blank=True)
    city       = models.CharField(max_length=100, blank=True)
    bio        = models.TextField(max_length=300, blank=True)
    support_preference = models.CharField(
        max_length=10, choices=SUPPORT_CHOICES, blank=True, default=''
    )
    is_blocked = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_support_display_label(self):
        mapping = {'talk': 'Open to Talk', 'listen': 'Prefer Listening', 'need': 'Needs Support'}
        return mapping.get(self.support_preference, '')

    def get_support_icon(self):
        mapping = {'talk': 'bi-chat-heart', 'listen': 'bi-ear', 'need': 'bi-heart-pulse'}
        return mapping.get(self.support_preference, 'bi-question-circle')

    def get_support_color(self):
        mapping = {'talk': '#34d399', 'listen': '#60a5fa', 'need': '#f87171'}
        return mapping.get(self.support_preference, '#94a3b8')
