from django.db import models
from django.contrib.auth.models import User


class Report(models.Model):
    PENDING  = 'pending'
    RESOLVED = 'resolved'
    IGNORED  = 'ignored'
    STATUS_CHOICES = [
        (PENDING,  'Pending'),
        (RESOLVED, 'Resolved'),
        (IGNORED,  'Ignored'),
    ]

    reporter      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='filed_reports')
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_reports')
    reason        = models.TextField(max_length=1000)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.reporter} reported {self.reported_user} [{self.status}]"


class AuditLog(models.Model):
    admin      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action     = models.CharField(max_length=200)
    target     = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.admin} — {self.action}"
