from django.db import models
from django.contrib.auth.models import User


class EmotionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    emotion_detected = models.CharField(max_length=50)
    confidence_score = models.FloatField(default=0.0)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.emotion_detected} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
