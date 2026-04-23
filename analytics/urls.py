from django.urls import path
from . import views

urlpatterns = [
    # User-facing
    path('reports/', views.reports, name='reports'),
    path('chart-image/', views.chart_image, name='chart_image'),
    path('api/chart-data/', views.chart_data, name='chart_data'),
    path('report-user/<int:user_id>/', views.submit_report, name='submit_report'),

    # Admin — overview
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),

    # Admin — users
    path('admin-panel/users/', views.admin_users, name='admin_users'),
    path('admin-panel/users/<int:user_id>/block/', views.admin_block_user, name='admin_block_user'),
    path('admin-panel/users/<int:user_id>/unblock/', views.admin_unblock_user, name='admin_unblock_user'),
    path('admin-panel/users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),

    # Admin — reports
    path('admin-panel/reports/', views.admin_reports, name='admin_reports'),
    path('admin-panel/reports/<int:report_id>/resolve/', views.admin_resolve_report, name='admin_resolve_report'),
    path('admin-panel/reports/<int:report_id>/ignore/', views.admin_ignore_report, name='admin_ignore_report'),
    path('admin-panel/reports/<int:report_id>/block/', views.admin_block_from_report, name='admin_block_from_report'),

    # Admin — analytics
    path('admin-panel/analytics/', views.admin_analytics, name='admin_analytics'),

    # Admin — exports
    path('admin-panel/export/users/', views.admin_export_users, name='admin_export_users'),
    path('admin-panel/export/reports/', views.admin_export_reports, name='admin_export_reports'),
]
