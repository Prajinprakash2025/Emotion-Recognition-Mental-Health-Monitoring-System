import csv
import io
from datetime import date, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from emotion_tracker.models import EmotionLog
from accounts.models import UserProfile
from .models import Report, AuditLog


# ── shared helpers ────────────────────────────────────────────────────────────

_STRESS_MAP = {
    'Angry':    (90, 5),
    'Fear':     (90, 5),
    'Disgust':  (90, 5),
    'Sad':      (75, 10),
    'Stressed': (85, 5),
    'Surprise': (50, 60),
    'Neutral':  (20, 50),
    'Happy':    (5,  95),
}

EMOTION_META = {
    'Happy':    {'pill': 'happy',    'icon': 'bi-emoji-smile',        'bar_color': '#fde047'},
    'Sad':      {'pill': 'sad',      'icon': 'bi-emoji-frown',        'bar_color': '#60a5fa'},
    'Angry':    {'pill': 'angry',    'icon': 'bi-emoji-angry',        'bar_color': '#f87171'},
    'Fear':     {'pill': 'fear',     'icon': 'bi-exclamation-circle', 'bar_color': '#a78bfa'},
    'Surprise': {'pill': 'surprise', 'icon': 'bi-emoji-surprise',     'bar_color': '#f472b6'},
    'Disgust':  {'pill': 'disgust',  'icon': 'bi-emoji-dizzy',        'bar_color': '#fb923c'},
    'Neutral':  {'pill': 'neutral',  'icon': 'bi-emoji-neutral',      'bar_color': '#94a3b8'},
    'Stressed': {'pill': 'angry',    'icon': 'bi-lightning',          'bar_color': '#f97316'},
}


def _emotion_to_scores(emotion):
    return _STRESS_MAP.get(emotion, (0, 0))


def _stress_level(stress_pct):
    if stress_pct >= 75:
        return 'High'
    if stress_pct >= 40:
        return 'Medium'
    return 'Low'


def _user_stress_level(user):
    logs = list(EmotionLog.objects.filter(user=user).order_by('-timestamp')[:50])
    if not logs:
        return 'Low'
    avg = sum(_emotion_to_scores(l.emotion_detected)[0] for l in logs) / len(logs)
    return _stress_level(avg)


def _audit(admin, action, target=''):
    AuditLog.objects.create(admin=admin, action=action, target=target)


def _is_admin(user):
    return user.is_active and user.is_staff


# ── user-facing reports ───────────────────────────────────────────────────────

@login_required
def reports(request):
    all_logs = EmotionLog.objects.filter(user=request.user).order_by('-timestamp')
    total = all_logs.count()

    dominant_emotion = 'N/A'
    avg_stress_label = 'N/A'
    last_emotion = 'N/A'
    emotion_distribution = []

    if total:
        dominant_qs = (
            all_logs.values('emotion_detected')
            .annotate(cnt=Count('emotion_detected'))
            .order_by('-cnt')
            .first()
        )
        dominant_emotion = dominant_qs['emotion_detected'] if dominant_qs else 'N/A'
        last_emotion = all_logs.first().emotion_detected

        stress_scores = [_emotion_to_scores(l.emotion_detected)[0] for l in all_logs[:200]]
        avg_stress = sum(stress_scores) / len(stress_scores) if stress_scores else 0
        avg_stress_label = _stress_level(avg_stress)

        dist_qs = (
            all_logs.values('emotion_detected')
            .annotate(cnt=Count('emotion_detected'))
            .order_by('-cnt')
        )
        for item in dist_qs:
            e = item['emotion_detected']
            pct = round((item['cnt'] / total) * 100, 1)
            meta = EMOTION_META.get(e, {'pill': 'neutral', 'icon': 'bi-circle', 'bar_color': '#94a3b8'})
            emotion_distribution.append({
                'emotion': e,
                'count': item['cnt'],
                'pct': pct,
                'pill': meta['pill'],
                'icon': meta['icon'],
                'bar_color': meta['bar_color'],
            })

    paginator = Paginator(all_logs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    annotated_logs = []
    for log in page_obj:
        stress_pct, _ = _emotion_to_scores(log.emotion_detected)
        meta = EMOTION_META.get(log.emotion_detected, {'pill': 'neutral', 'icon': 'bi-circle'})
        annotated_logs.append({
            'log': log,
            'stress_level': _stress_level(stress_pct),
            'pill_class': meta['pill'],
            'icon': meta['icon'],
        })

    context = {
        'logs': page_obj,
        'annotated_logs': annotated_logs,
        'total': total,
        'dominant_emotion': dominant_emotion,
        'dominant_meta': EMOTION_META.get(dominant_emotion, {'pill': 'neutral', 'icon': 'bi-circle'}),
        'avg_stress_label': avg_stress_label,
        'last_emotion': last_emotion,
        'last_meta': EMOTION_META.get(last_emotion, {'pill': 'neutral', 'icon': 'bi-circle'}),
        'emotion_distribution': emotion_distribution,
    }
    return render(request, 'analytics/reports.html', context)


@login_required
def chart_image(request):
    logs = list(EmotionLog.objects.filter(user=request.user).order_by('-timestamp')[:30])[::-1]
    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)

    if not logs:
        ax.text(0.5, 0.5, 'No Data Available', ha='center', va='center', color='white', fontsize=13)
        ax.axis('off')
    else:
        timestamps = [log.timestamp.strftime('%H:%M:%S') for log in logs]
        stress_vals, happiness_vals = zip(*[_emotion_to_scores(log.emotion_detected) for log in logs])
        sns.set_style("darkgrid")
        plt.rcParams.update({
            "axes.facecolor": "#00000000", "figure.facecolor": "#00000000",
            "savefig.facecolor": "#00000000", "text.color": "white",
            "axes.labelcolor": "white", "xtick.color": "white",
            "ytick.color": "white", "grid.color": "#444444"
        })
        sns.lineplot(x=timestamps, y=stress_vals, ax=ax, color='#ff4d4d', label='Stress', linewidth=2, marker='o')
        sns.lineplot(x=timestamps, y=happiness_vals, ax=ax, color='#4d79ff', label='Happiness', linewidth=2, marker='o')
        ax.set_ylim(0, 100)
        ax.set_xticks(range(len(timestamps)))
        ax.set_xticklabels(timestamps, rotation=45, ha='right')
        ax.legend(facecolor='#222', edgecolor='#444', labelcolor='white')
        ax.set_title('Emotional Trends', color='white', fontsize=12)
        if len(timestamps) > 10:
            ax.xaxis.set_major_locator(plt.MaxNLocator(10))

    plt.tight_layout()
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', transparent=True)
    plt.close(fig)
    return HttpResponse(buffer.getvalue(), content_type='image/png')


@login_required
def chart_data(request):
    logs = list(EmotionLog.objects.filter(user=request.user).order_by('-timestamp')[:30])[::-1]
    labels, stress_levels, happiness_levels = [], [], []
    for log in logs:
        labels.append(timezone.localtime(log.timestamp).strftime('%H:%M:%S'))
        s, h = _emotion_to_scores(log.emotion_detected)
        stress_levels.append(s)
        happiness_levels.append(h)
    return JsonResponse({'labels': labels, 'stress_levels': stress_levels, 'happiness_levels': happiness_levels})


# ── user report submission ────────────────────────────────────────────────────

@login_required
@require_POST
def submit_report(request, user_id):
    reported = get_object_or_404(User, id=user_id)
    if reported == request.user:
        return redirect('user_profile', user_id=user_id)
    reason = request.POST.get('reason', '').strip()
    if reason:
        Report.objects.create(reporter=request.user, reported_user=reported, reason=reason)
    return redirect('user_profile', user_id=user_id)


# ── admin guard ───────────────────────────────────────────────────────────────

def _admin_required(view_fn):
    return login_required(user_passes_test(_is_admin, login_url='/login/')(view_fn))


def _pending_reports_count():
    return Report.objects.filter(status=Report.PENDING).count()


# ── admin: overview dashboard ─────────────────────────────────────────────────

@_admin_required
def admin_dashboard(request):
    now = timezone.now()
    cutoff_24h = now - timedelta(hours=24)

    total_users   = User.objects.count()
    active_users  = User.objects.filter(last_login__gte=cutoff_24h).count()
    total_sessions = EmotionLog.objects.count()
    total_reports  = Report.objects.count()
    pending_reports = Report.objects.filter(status=Report.PENDING).count()
    blocked_users  = UserProfile.objects.filter(is_blocked=True).count()

    # High-stress: avg stress >= 75 across last 50 logs
    high_stress_count = 0
    for user in User.objects.filter(is_active=True, is_staff=False):
        if _user_stress_level(user) == 'High':
            high_stress_count += 1

    # Emotion distribution for bar chart
    emotion_dist = (
        EmotionLog.objects.values('emotion_detected')
        .annotate(cnt=Count('emotion_detected'))
        .order_by('-cnt')
    )
    chart_labels  = [e['emotion_detected'] for e in emotion_dist]
    chart_counts  = [e['cnt'] for e in emotion_dist]
    chart_colors  = [EMOTION_META.get(e, {}).get('bar_color', '#94a3b8') for e in chart_labels]

    # Daily active users — last 7 days
    dau_labels, dau_counts = [], []
    for i in range(6, -1, -1):
        day = (now - timedelta(days=i)).date()
        cnt = EmotionLog.objects.filter(timestamp__date=day).values('user').distinct().count()
        dau_labels.append(day.strftime('%b %d'))
        dau_counts.append(cnt)

    # Stress breakdown
    stress_counts = {'High': 0, 'Medium': 0, 'Low': 0}
    for user in User.objects.filter(is_active=True, is_staff=False):
        stress_counts[_user_stress_level(user)] += 1

    recent_logs  = EmotionLog.objects.select_related('user').order_by('-timestamp')[:8]
    audit_logs   = AuditLog.objects.select_related('admin').order_by('-created_at')[:10]

    context = {
        'total_users':      total_users,
        'active_users':     active_users,
        'total_sessions':   total_sessions,
        'high_stress_count': high_stress_count,
        'total_reports':    total_reports,
        'pending_reports':  pending_reports,
        'blocked_users':    blocked_users,
        'chart_labels':     chart_labels,
        'chart_counts':     chart_counts,
        'chart_colors':     chart_colors,
        'dau_labels':       dau_labels,
        'dau_counts':       dau_counts,
        'stress_counts':    stress_counts,
        'recent_logs':      recent_logs,
        'audit_logs':       audit_logs,
        'pending_reports_count': pending_reports,
        'active_section':   'dashboard',
    }
    return render(request, 'analytics/admin_dashboard.html', context)


# ── admin: user management ────────────────────────────────────────────────────

@_admin_required
def admin_users(request):
    q       = request.GET.get('q', '').strip()
    filt    = request.GET.get('filter', 'all')

    users_qs = User.objects.filter(is_staff=False).select_related('profile').order_by('-date_joined')

    if q:
        users_qs = users_qs.filter(Q(username__icontains=q) | Q(email__icontains=q))

    if filt == 'active':
        cutoff = timezone.now() - timedelta(hours=24)
        users_qs = users_qs.filter(last_login__gte=cutoff)
    elif filt == 'blocked':
        users_qs = users_qs.filter(profile__is_blocked=True)
    elif filt == 'high_stress':
        # pull IDs then filter — avoids N+1 for small sets
        high_ids = [u.id for u in users_qs if _user_stress_level(u) == 'High']
        users_qs = users_qs.filter(id__in=high_ids)

    paginator = Paginator(users_qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    rows = []
    for user in page_obj:
        prof, _ = UserProfile.objects.get_or_create(user=user)
        rows.append({
            'user':         user,
            'profile':      prof,
            'stress_level': _user_stress_level(user),
            'last_active':  user.last_login,
        })

    context = {
        'rows':           rows,
        'page_obj':       page_obj,
        'q':              q,
        'filter':         filt,
        'pending_reports_count': _pending_reports_count(),
        'active_section': 'users',
    }
    return render(request, 'analytics/admin_users.html', context)


@_admin_required
@require_POST
def admin_block_user(request, user_id):
    target = get_object_or_404(User, id=user_id)
    prof, _ = UserProfile.objects.get_or_create(user=target)
    prof.is_blocked = True
    prof.save()
    target.is_active = False
    target.save()
    _audit(request.user, f'Blocked user', target.username)
    return redirect(request.POST.get('next', 'admin_users'))


@_admin_required
@require_POST
def admin_unblock_user(request, user_id):
    target = get_object_or_404(User, id=user_id)
    prof, _ = UserProfile.objects.get_or_create(user=target)
    prof.is_blocked = False
    prof.save()
    target.is_active = True
    target.save()
    _audit(request.user, f'Unblocked user', target.username)
    return redirect(request.POST.get('next', 'admin_users'))


@_admin_required
@require_POST
def admin_delete_user(request, user_id):
    target = get_object_or_404(User, id=user_id)
    username = target.username
    target.delete()
    _audit(request.user, 'Deleted user', username)
    return redirect('admin_users')


# ── admin: reports management ─────────────────────────────────────────────────

@_admin_required
def admin_reports(request):
    filt = request.GET.get('filter', 'all')
    qs   = Report.objects.select_related('reporter', 'reported_user').order_by('-created_at')

    if filt == 'pending':
        qs = qs.filter(status=Report.PENDING)
    elif filt == 'resolved':
        qs = qs.filter(status=Report.RESOLVED)
    elif filt == 'ignored':
        qs = qs.filter(status=Report.IGNORED)

    paginator = Paginator(qs, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj':       page_obj,
        'filter':         filt,
        'pending_reports_count': _pending_reports_count(),
        'active_section': 'reports',
    }
    return render(request, 'analytics/admin_reports.html', context)


@_admin_required
@require_POST
def admin_resolve_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    report.status = Report.RESOLVED
    report.save()
    _audit(request.user, 'Resolved report', f'Report #{report_id}')
    return redirect(request.POST.get('next', 'admin_reports'))


@_admin_required
@require_POST
def admin_ignore_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    report.status = Report.IGNORED
    report.save()
    _audit(request.user, 'Ignored report', f'Report #{report_id}')
    return redirect(request.POST.get('next', 'admin_reports'))


@_admin_required
@require_POST
def admin_block_from_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    target = report.reported_user
    prof, _ = UserProfile.objects.get_or_create(user=target)
    prof.is_blocked = True
    prof.save()
    target.is_active = False
    target.save()
    report.status = Report.RESOLVED
    report.save()
    _audit(request.user, 'Blocked user via report', target.username)
    return redirect(request.POST.get('next', 'admin_reports'))


# ── admin: analytics ──────────────────────────────────────────────────────────

@_admin_required
def admin_analytics(request):
    now = timezone.now()

    # Emotion distribution
    emotion_dist = (
        EmotionLog.objects.values('emotion_detected')
        .annotate(cnt=Count('emotion_detected'))
        .order_by('-cnt')
    )
    chart_labels = [e['emotion_detected'] for e in emotion_dist]
    chart_counts = [e['cnt'] for e in emotion_dist]
    chart_colors = [EMOTION_META.get(e, {}).get('bar_color', '#94a3b8') for e in chart_labels]

    # Daily active users — last 14 days
    dau_labels, dau_counts = [], []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        cnt = EmotionLog.objects.filter(timestamp__date=day).values('user').distinct().count()
        dau_labels.append(day.strftime('%b %d'))
        dau_counts.append(cnt)

    # Stress breakdown
    stress_counts = {'High': 0, 'Medium': 0, 'Low': 0}
    for user in User.objects.filter(is_active=True, is_staff=False):
        stress_counts[_user_stress_level(user)] += 1

    # High-risk users
    high_risk = []
    for user in User.objects.filter(is_active=True, is_staff=False).order_by('-last_login')[:100]:
        if _user_stress_level(user) == 'High':
            last_log = EmotionLog.objects.filter(user=user).order_by('-timestamp').first()
            high_risk.append({
                'user':      user,
                'last_log':  last_log,
            })
        if len(high_risk) >= 20:
            break

    context = {
        'chart_labels':   chart_labels,
        'chart_counts':   chart_counts,
        'chart_colors':   chart_colors,
        'dau_labels':     dau_labels,
        'dau_counts':     dau_counts,
        'stress_counts':  stress_counts,
        'high_risk':      high_risk,
        'pending_reports_count': _pending_reports_count(),
        'active_section': 'analytics',
    }
    return render(request, 'analytics/admin_analytics.html', context)


# ── admin: export CSV ─────────────────────────────────────────────────────────

@_admin_required
def admin_export_users(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Username', 'Email', 'Date Joined', 'Last Login', 'Blocked', 'Stress Level'])
    for user in User.objects.filter(is_staff=False).select_related('profile').order_by('id'):
        prof = getattr(user, 'profile', None)
        writer.writerow([
            user.id, user.username, user.email,
            user.date_joined.strftime('%Y-%m-%d'),
            user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else '',
            'Yes' if (prof and prof.is_blocked) else 'No',
            _user_stress_level(user),
        ])
    _audit(request.user, 'Exported users CSV')
    return response


@_admin_required
def admin_export_reports(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reports_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['ID', 'Reporter', 'Reported User', 'Reason', 'Status', 'Date'])
    for r in Report.objects.select_related('reporter', 'reported_user').order_by('id'):
        writer.writerow([
            r.id, r.reporter.username, r.reported_user.username,
            r.reason, r.status, r.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    _audit(request.user, 'Exported reports CSV')
    return response
