import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from emotion_tracker.models import EmotionLog
from .models import ChatMessage, Connection, ActivitySession

# ── emotion helpers (untouched) ───────────────────────────────────────────────

SUGGESTIONS = {
    'negative': [
        {'icon': 'bi-wind',             'text': 'Try 4-7-8 breathing: inhale 4s, hold 7s, exhale 8s.'},
        {'icon': 'bi-person-walking',   'text': 'Take a short 10-minute walk outside.'},
        {'icon': 'bi-chat-heart',       'text': 'Talk to someone you trust about how you feel.'},
        {'icon': 'bi-music-note-beamed','text': 'Listen to calming or uplifting music.'},
    ],
    'happy': [
        {'icon': 'bi-star',          'text': 'Keep up your good habits — consistency is key!'},
        {'icon': 'bi-people',        'text': 'Share your positivity with someone around you.'},
        {'icon': 'bi-journal-text',  'text': 'Write 3 things you are grateful for today.'},
        {'icon': 'bi-emoji-smile',   'text': 'Celebrate small wins — you deserve it!'},
    ],
    'neutral': [
        {'icon': 'bi-yin-yang',       'text': 'Practice mindful breathing for 5 minutes.'},
        {'icon': 'bi-calendar-check', 'text': 'Set one small, achievable goal for today.'},
        {'icon': 'bi-cup-hot',        'text': 'Take a break and enjoy a warm drink mindfully.'},
        {'icon': 'bi-book',           'text': 'Read something inspiring or educational.'},
    ],
}


def _get_emotion_data(user):
    logs = EmotionLog.objects.filter(user=user).order_by('-timestamp')[:50]
    if not logs:
        return 'Neutral', {}, 'neutral'
    counts = {}
    for log in logs:
        counts[log.emotion_detected] = counts.get(log.emotion_detected, 0) + 1
    total = sum(counts.values())
    percentages = {e: round((c / total) * 100, 1) for e, c in counts.items()}
    dominant = max(counts, key=counts.get)
    category = (
        'negative' if dominant in ('Sad', 'Angry', 'Fear', 'Disgust', 'Stressed')
        else 'happy' if dominant == 'Happy'
        else 'neutral'
    )
    return dominant, percentages, category


# ── chat helpers ──────────────────────────────────────────────────────────────

def _avatar(username):
    return ChatMessage.avatar(username)


def _serialize_msg(msg, current_user_id):
    return {
        'id':          msg.id,
        'username':    msg.sender.username,
        'avatar':      _avatar(msg.sender.username),
        'message':     msg.message,
        'timestamp':   msg.timestamp.strftime('%H:%M'),
        'is_self':     msg.sender_id == current_user_id,
        'is_private':  msg.is_private,
        'profile_url': f'/user/{msg.sender_id}/',
    }


def _connected_users(user):
    """Return queryset of User objects that are accepted connections of `user`."""
    accepted = Connection.objects.filter(
        status=Connection.ACCEPTED
    ).filter(Q(sender=user) | Q(receiver=user))

    ids = set()
    for c in accepted:
        ids.add(c.receiver_id if c.sender_id == user.id else c.sender_id)
    return User.objects.filter(id__in=ids).order_by('username')


def _pending_count(user):
    return Connection.objects.filter(receiver=user, status=Connection.PENDING).count()


def _build_sidebar(current_user, active_peer_id=None):
    connected = _connected_users(current_user)
    rows = []
    for u in connected:
        last_pm = (
            ChatMessage.objects
            .filter(is_private=True)
            .filter(Q(sender=current_user, receiver=u) | Q(sender=u, receiver=current_user))
            .order_by('-timestamp')
            .first()
        )
        rows.append({
            'id':       u.id,
            'username': u.username,
            'avatar':   _avatar(u.username),
            'last_msg': last_pm.message[:30] if last_pm else '',
            'last_ts':  last_pm.timestamp.strftime('%H:%M') if last_pm else '',
            'active':   u.id == active_peer_id,
        })
    return rows


# ── standard pages ────────────────────────────────────────────────────────────

def home(request):
    return render(request, 'dashboard/home.html')


def about(request):
    return render(request, 'dashboard/about.html')


def contact(request):
    if request.method == 'POST':
        messages.success(request, "Thanks for your message! We'll get back to you within 24 hours.")
        return redirect('contact')
    return render(request, 'dashboard/contact.html')


def help_page(request):
    return render(request, 'dashboard/help.html')


_STRESS_MAP = {
    'Angry': 90, 'Fear': 90, 'Disgust': 90, 'Stressed': 85,
    'Sad': 75, 'Surprise': 50, 'Neutral': 20, 'Happy': 5,
}


def _get_stress_level(user):
    """Return 'High', 'Medium', or 'Low' based on last 50 logs."""
    logs = list(EmotionLog.objects.filter(user=user).order_by('-timestamp')[:50])
    if not logs:
        return 'Low'
    avg = sum(_STRESS_MAP.get(l.emotion_detected, 0) for l in logs) / len(logs)
    if avg >= 75:
        return 'High'
    if avg >= 40:
        return 'Medium'
    return 'Low'


def _active_participants(activity_type, exclude_user):
    """Return list of dicts for users currently active in an activity (last 30 min)."""
    cutoff = timezone.now() - timedelta(minutes=30)
    sessions = (
        ActivitySession.objects
        .filter(activity_type=activity_type, status=ActivitySession.ACTIVE, updated__gte=cutoff)
        .exclude(user=exclude_user)
        .select_related('user')
        .order_by('-updated')[:8]
    )
    return [
        {'username': s.user.username, 'avatar': ChatMessage.avatar(s.user.username)}
        for s in sessions
    ]


@login_required
def main_dashboard(request):
    dominant_emotion, emotion_percentages, suggestion_category = _get_emotion_data(request.user)
    stress_level = _get_stress_level(request.user)
    # Show relief section for negative emotions, high stress, OR no data yet (always show for new users)
    _negative = {'Sad', 'Angry', 'Fear', 'Disgust', 'Stressed'}
    show_relief = dominant_emotion in _negative or stress_level == 'High' or dominant_emotion == 'Neutral'

    # Current user's active session (if any) for button state
    cutoff = timezone.now() - timedelta(minutes=30)
    my_active = set(
        ActivitySession.objects
        .filter(user=request.user, status=ActivitySession.ACTIVE, updated__gte=cutoff)
        .values_list('activity_type', flat=True)
    )

    activities = [
        {
            'key':          ActivitySession.BREATHING,
            'label':        'Breathing Exercise',
            'icon':         'bi-wind',
            'color':        '#34d399',
            'bg':           'rgba(16,185,129,0.12)',
            'participants': _active_participants(ActivitySession.BREATHING, request.user),
            'joined':       ActivitySession.BREATHING in my_active,
        },
        {
            'key':          ActivitySession.GAME,
            'label':        'Mood Game',
            'icon':         'bi-controller',
            'color':        '#60a5fa',
            'bg':           'rgba(59,130,246,0.12)',
            'participants': _active_participants(ActivitySession.GAME, request.user),
            'joined':       ActivitySession.GAME in my_active,
        },
        {
            'key':          ActivitySession.MUSIC,
            'label':        'Music Therapy',
            'icon':         'bi-music-note-beamed',
            'color':        '#a78bfa',
            'bg':           'rgba(167,139,250,0.12)',
            'participants': _active_participants(ActivitySession.MUSIC, request.user),
            'joined':       ActivitySession.MUSIC in my_active,
        },
        {
            'key':          ActivitySession.CHALLENGE,
            'label':        'Positive Challenge',
            'icon':         'bi-trophy',
            'color':        '#fbbf24',
            'bg':           'rgba(251,191,36,0.12)',
            'participants': _active_participants(ActivitySession.CHALLENGE, request.user),
            'joined':       ActivitySession.CHALLENGE in my_active,
        },
    ]

    context = {
        'dominant_emotion':    dominant_emotion,
        'emotion_percentages': emotion_percentages,
        'suggestions':         SUGGESTIONS[suggestion_category],
        'suggestion_category': suggestion_category,
        'pending_count':       _pending_count(request.user),
        'stress_level':        stress_level,
        'show_relief':         show_relief,
        'activities':          activities,
        'activities_json':     json.dumps(activities),
    }
    return render(request, 'dashboard/index.html', context)


# ── connection views ──────────────────────────────────────────────────────────

@login_required
@require_POST
def send_connection_request(request, user_id):
    target = get_object_or_404(User, id=user_id)
    if target == request.user:
        return redirect('user_profile', user_id=user_id)
    # Avoid duplicate — if rejected before, allow re-request by updating
    conn, created = Connection.objects.get_or_create(
        sender=request.user, receiver=target,
        defaults={'status': Connection.PENDING}
    )
    if not created and conn.status == Connection.REJECTED:
        conn.status = Connection.PENDING
        conn.save()
    return redirect('user_profile', user_id=user_id)


@login_required
@require_POST
def accept_connection(request, connection_id):
    conn = get_object_or_404(Connection, id=connection_id, receiver=request.user)
    conn.status = Connection.ACCEPTED
    conn.save()
    return redirect(request.POST.get('next', 'connections_page'))


@login_required
@require_POST
def reject_connection(request, connection_id):
    conn = get_object_or_404(Connection, id=connection_id, receiver=request.user)
    conn.status = Connection.REJECTED
    conn.save()
    return redirect(request.POST.get('next', 'connections_page'))


@login_required
@require_POST
def remove_connection(request, user_id):
    target = get_object_or_404(User, id=user_id)
    Connection.objects.filter(
        status=Connection.ACCEPTED
    ).filter(
        Q(sender=request.user, receiver=target) | Q(sender=target, receiver=request.user)
    ).delete()
    return redirect('user_profile', user_id=user_id)


@login_required
def connections_page(request):
    """Lists pending incoming requests + all accepted connections."""
    pending_in = Connection.objects.filter(
        receiver=request.user, status=Connection.PENDING
    ).select_related('sender')

    pending_out = Connection.objects.filter(
        sender=request.user, status=Connection.PENDING
    ).select_related('receiver')

    connected = _connected_users(request.user)

    context = {
        'pending_in':    pending_in,
        'pending_out':   pending_out,
        'connected':     connected,
        'pending_count': pending_in.count(),
    }
    return render(request, 'dashboard/connections.html', context)


# ── chat pages ────────────────────────────────────────────────────────────────

@login_required
def chat_page(request):
    global_msgs = (
        ChatMessage.objects
        .filter(is_private=False)
        .select_related('sender')
        .order_by('timestamp')[:200]
    )
    serialized = [_serialize_msg(m, request.user.id) for m in global_msgs]
    context = {
        'global_messages': serialized,
        'last_id':         serialized[-1]['id'] if serialized else 0,
        'user_list':       _build_sidebar(request.user),
        'chat_mode':       'global',
        'peer':            None,
        'can_message':     True,
        'pending_count':   _pending_count(request.user),
    }
    return render(request, 'dashboard/chat.html', context)


@login_required
def private_chat(request, user_id):
    peer = get_object_or_404(User, id=user_id)
    if peer == request.user:
        return redirect('chat_page')

    can_message = Connection.are_connected(request.user, peer)

    pm_msgs = []
    if can_message:
        qs = (
            ChatMessage.objects
            .filter(is_private=True)
            .filter(Q(sender=request.user, receiver=peer) | Q(sender=peer, receiver=request.user))
            .select_related('sender')
            .order_by('timestamp')[:200]
        )
        pm_msgs = [_serialize_msg(m, request.user.id) for m in qs]

    context = {
        'global_messages': [],
        'last_id':         pm_msgs[-1]['id'] if pm_msgs else 0,
        'user_list':       _build_sidebar(request.user, active_peer_id=peer.id),
        'chat_mode':       'private',
        'peer': {
            'id':       peer.id,
            'username': peer.username,
            'avatar':   _avatar(peer.username),
        },
        'pm_messages':   pm_msgs,
        'can_message':   can_message,
        'pending_count': _pending_count(request.user),
    }
    return render(request, 'dashboard/chat.html', context)


# ── message APIs ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def send_message(request):
    try:
        data        = json.loads(request.body)
        text        = data.get('message', '').strip()
        is_private  = bool(data.get('is_private', False))
        receiver_id = data.get('receiver_id')

        if not text:
            return JsonResponse({'error': 'Empty message'}, status=400)

        receiver = None
        if is_private:
            if not receiver_id:
                return JsonResponse({'error': 'receiver_id required'}, status=400)
            receiver = get_object_or_404(User, id=receiver_id)
            if not Connection.are_connected(request.user, receiver):
                return JsonResponse(
                    {'error': 'You must be connected to send private messages.'},
                    status=403
                )

        msg = ChatMessage.objects.create(
            sender=request.user,
            receiver=receiver,
            message=text,
            is_private=is_private,
        )
        return JsonResponse(_serialize_msg(msg, request.user.id))
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def poll_global(request):
    after_id = int(request.GET.get('after', 0))
    msgs = (
        ChatMessage.objects
        .filter(is_private=False, id__gt=after_id)
        .select_related('sender')
        .order_by('timestamp')[:50]
    )
    return JsonResponse({'messages': [_serialize_msg(m, request.user.id) for m in msgs]})


@login_required
def poll_private(request, user_id):
    peer = get_object_or_404(User, id=user_id)
    if not Connection.are_connected(request.user, peer):
        return JsonResponse({'messages': []})
    after_id = int(request.GET.get('after', 0))
    msgs = (
        ChatMessage.objects
        .filter(is_private=True, id__gt=after_id)
        .filter(Q(sender=request.user, receiver=peer) | Q(sender=peer, receiver=request.user))
        .select_related('sender')
        .order_by('timestamp')[:50]
    )
    return JsonResponse({'messages': [_serialize_msg(m, request.user.id) for m in msgs]})


# ── activity APIs ────────────────────────────────────────────────────────────

@login_required
@require_POST
def join_activity(request, activity_type):
    valid = {ActivitySession.BREATHING, ActivitySession.GAME,
             ActivitySession.MUSIC, ActivitySession.CHALLENGE}
    if activity_type not in valid:
        return JsonResponse({'error': 'Invalid activity'}, status=400)

    cutoff = timezone.now() - timedelta(minutes=30)
    # Upsert: reuse existing active session or create new one
    session = (
        ActivitySession.objects
        .filter(user=request.user, activity_type=activity_type,
                status=ActivitySession.ACTIVE, updated__gte=cutoff)
        .first()
    )
    if not session:
        session = ActivitySession.objects.create(
            user=request.user,
            activity_type=activity_type,
            status=ActivitySession.ACTIVE,
        )
    else:
        session.save()  # bumps `updated` timestamp

    participants = _active_participants(activity_type, request.user)
    return JsonResponse({
        'joined':       True,
        'count':        len(participants) + 1,
        'participants': participants,
    })


@login_required
@require_POST
def leave_activity(request, activity_type):
    ActivitySession.objects.filter(
        user=request.user,
        activity_type=activity_type,
        status=ActivitySession.ACTIVE,
    ).update(status=ActivitySession.COMPLETED)
    return JsonResponse({'joined': False, 'count': len(_active_participants(activity_type, request.user))})


@login_required
def activity_status(request, activity_type):
    cutoff = timezone.now() - timedelta(minutes=30)
    participants = _active_participants(activity_type, request.user)
    my_active = ActivitySession.objects.filter(
        user=request.user, activity_type=activity_type,
        status=ActivitySession.ACTIVE, updated__gte=cutoff,
    ).exists()
    return JsonResponse({
        'joined':       my_active,
        'count':        len(participants) + (1 if my_active else 0),
        'participants': participants,
    })


# ── legacy aliases ────────────────────────────────────────────────────────────

@login_required
@require_POST
def send_chat_message(request):
    return send_message(request)


@login_required
def get_chat_messages(request):
    return poll_global(request)
