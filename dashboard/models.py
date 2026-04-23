from django.db import models
from django.contrib.auth.models import User


class Connection(models.Model):
    PENDING  = 'pending'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    STATUS_CHOICES = [
        (PENDING,  'Pending'),
        (ACCEPTED, 'Accepted'),
        (REJECTED, 'Rejected'),
    ]

    sender   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    status   = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')
        ordering = ['-created']

    def __str__(self):
        return f"{self.sender} → {self.receiver} [{self.status}]"

    @classmethod
    def are_connected(cls, user_a, user_b):
        return cls.objects.filter(
            status=cls.ACCEPTED
        ).filter(
            models.Q(sender=user_a, receiver=user_b) |
            models.Q(sender=user_b, receiver=user_a)
        ).exists()

    @classmethod
    def get_connection(cls, user_a, user_b):
        return cls.objects.filter(
            models.Q(sender=user_a, receiver=user_b) |
            models.Q(sender=user_b, receiver=user_a)
        ).first()


class ActivitySession(models.Model):
    BREATHING = 'breathing'
    GAME      = 'game'
    MUSIC     = 'music'
    CHALLENGE = 'challenge'
    ACTIVITY_CHOICES = [
        (BREATHING, 'Breathing Exercise'),
        (GAME,      'Mood Game'),
        (MUSIC,     'Music Therapy'),
        (CHALLENGE, 'Positive Challenge'),
    ]
    ACTIVE    = 'active'
    COMPLETED = 'completed'
    STATUS_CHOICES = [
        (ACTIVE,    'Active'),
        (COMPLETED, 'Completed'),
    ]

    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_sessions')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default=ACTIVE)
    timestamp     = models.DateTimeField(auto_now_add=True)
    updated       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} — {self.activity_type} [{self.status}]"


class ChatMessage(models.Model):
    sender   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages',
                                 null=True, blank=True)
    message    = models.TextField()
    is_private = models.BooleanField(default=False)
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username if self.receiver else 'global'}: {self.message[:40]}"

    @staticmethod
    def avatar(username):
        return f"https://ui-avatars.com/api/?name={username}&background=3b82f6&color=fff&size=64&bold=true"
