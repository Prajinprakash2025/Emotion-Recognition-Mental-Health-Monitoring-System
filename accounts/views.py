from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Avg
from django.utils import timezone

from .forms import SignupForm
from .models import UserProfile
from emotion_tracker.models import EmotionLog
from dashboard.models import Connection

# Stress score mapping (reused from analytics)
_STRESS_MAP = {
    'Angry': 90, 'Fear': 90, 'Disgust': 90, 'Stressed': 85,
    'Sad': 75, 'Surprise': 50, 'Neutral': 20, 'Happy': 5,
}

EMOTION_PILL = {
    'Happy':    'happy',
    'Sad':      'sad',
    'Angry':    'angry',
    'Fear':     'fear',
    'Surprise': 'surprise',
    'Disgust':  'disgust',
    'Neutral':  'neutral',
    'Stressed': 'angry',
}


def _build_analytics(user):
    """Return analytics dict for a given user's EmotionLog history."""
    logs = EmotionLog.objects.filter(user=user).order_by('-timestamp')
    total = logs.count()
    if not total:
        return {
            'total_sessions': 0,
            'most_common': 'No Data',
            'most_common_pill': 'neutral',
            'stress_label': 'N/A',
            'stress_color': '#94a3b8',
            'last_active': None,
            'emotion_distribution': [],
            'trend': 'stable',
            'trend_icon': 'bi-dash',
            'trend_color': '#94a3b8',
        }

    # Dominant emotion
    dominant_qs = (
        logs.values('emotion_detected')
        .annotate(cnt=Count('emotion_detected'))
        .order_by('-cnt')
        .first()
    )
    dominant = dominant_qs['emotion_detected'] if dominant_qs else 'Neutral'

    # Average stress
    stress_scores = [_STRESS_MAP.get(l.emotion_detected, 0) for l in logs[:100]]
    avg_stress = sum(stress_scores) / len(stress_scores) if stress_scores else 0
    if avg_stress >= 75:
        stress_label, stress_color = 'High', '#f87171'
    elif avg_stress >= 40:
        stress_label, stress_color = 'Medium', '#fb923c'
    else:
        stress_label, stress_color = 'Low', '#34d399'

    # Trend: compare last 10 vs previous 10
    recent  = [_STRESS_MAP.get(l.emotion_detected, 0) for l in logs[:10]]
    older   = [_STRESS_MAP.get(l.emotion_detected, 0) for l in logs[10:20]]
    if recent and older:
        diff = (sum(recent) / len(recent)) - (sum(older) / len(older))
        if diff < -5:
            trend, trend_icon, trend_color = 'Improving', 'bi-arrow-down-circle-fill', '#34d399'
        elif diff > 5:
            trend, trend_icon, trend_color = 'Declining', 'bi-arrow-up-circle-fill', '#f87171'
        else:
            trend, trend_icon, trend_color = 'Stable', 'bi-dash-circle-fill', '#94a3b8'
    else:
        trend, trend_icon, trend_color = 'Stable', 'bi-dash-circle-fill', '#94a3b8'

    # Distribution (top 5)
    dist_qs = (
        logs.values('emotion_detected')
        .annotate(cnt=Count('emotion_detected'))
        .order_by('-cnt')[:5]
    )
    distribution = [
        {
            'emotion': d['emotion_detected'],
            'pct': round((d['cnt'] / total) * 100, 1),
            'pill': EMOTION_PILL.get(d['emotion_detected'], 'neutral'),
        }
        for d in dist_qs
    ]

    return {
        'total_sessions':       total,
        'most_common':          dominant,
        'most_common_pill':     EMOTION_PILL.get(dominant, 'neutral'),
        'stress_label':         stress_label,
        'stress_color':         stress_color,
        'last_active':          logs.first().timestamp if logs.exists() else None,
        'emotion_distribution': distribution,
        'trend':                trend,
        'trend_icon':           trend_icon,
        'trend_color':          trend_color,
    }


def blocked_page(request):
    return render(request, 'accounts/blocked.html')


def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignupForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def profile(request):
    """Owner's own profile — full access + editable bio/preference."""
    prof, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        prof.bio = request.POST.get('bio', '').strip()[:300]
        prof.support_preference = request.POST.get('support_preference', '')
        prof.save()
        return redirect('profile')

    analytics = _build_analytics(request.user)
    return render(request, 'accounts/profile.html', {
        **analytics,
        'profile': prof,
    })


@login_required
def user_profile(request, user_id):
    """Public profile — privacy-gated sections based on connection status."""
    viewed_user = get_object_or_404(User, id=user_id)
    if viewed_user == request.user:
        return redirect('profile')

    prof, _ = UserProfile.objects.get_or_create(user=viewed_user)

    # Connection state
    conn          = Connection.get_connection(request.user, viewed_user)
    conn_status   = conn.status if conn else None
    is_sender     = conn.sender_id == request.user.id if conn else False
    is_connected  = conn_status == Connection.ACCEPTED
    is_pending_out = conn_status == Connection.PENDING and is_sender
    is_pending_in  = conn_status == Connection.PENDING and not is_sender

    # Always compute public stats
    logs_qs = EmotionLog.objects.filter(user=viewed_user)
    total_sessions = logs_qs.count()
    # Last active: only the date portion — not sensitive
    last_log = logs_qs.order_by('-timestamp').first()
    last_active_public = last_log.timestamp if last_log else None

    # Private analytics — only computed when connected (never sent to template otherwise)
    analytics = _build_analytics(viewed_user) if is_connected else None

    return render(request, 'accounts/user_profile.html', {
        'viewed_user':       viewed_user,
        'profile':           prof,
        'total_sessions':    total_sessions,
        'last_active_public': last_active_public,
        'analytics':         analytics,
        'is_connected':      is_connected,
        'is_pending_out':    is_pending_out,
        'is_pending_in':     is_pending_in,
        'conn':              conn,
    })
