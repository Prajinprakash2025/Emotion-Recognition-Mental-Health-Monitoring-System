from django.contrib import admin
from .models import EmotionLog

@admin.register(EmotionLog)
class EmotionLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'emotion_detected', 'confidence_score', 'timestamp']
    list_filter = ['emotion_detected']
    search_fields = ['user__username']
