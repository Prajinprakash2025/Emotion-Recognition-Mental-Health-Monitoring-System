from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('help/', views.help_page, name='help_page'),
    path('dashboard/', views.main_dashboard, name='dashboard'),

    # Connection management
    path('connections/', views.connections_page, name='connections_page'),
    path('connect/<int:user_id>/', views.send_connection_request, name='send_connection_request'),
    path('connect/accept/<int:connection_id>/', views.accept_connection, name='accept_connection'),
    path('connect/reject/<int:connection_id>/', views.reject_connection, name='reject_connection'),
    path('connect/remove/<int:user_id>/', views.remove_connection, name='remove_connection'),

    # Chat pages
    path('chat/', views.chat_page, name='chat_page'),
    path('chat/<int:user_id>/', views.private_chat, name='private_chat'),

    # Chat APIs
    path('api/chat/send/', views.send_message, name='send_message'),
    path('api/chat/global/poll/', views.poll_global, name='poll_global'),
    path('api/chat/private/<int:user_id>/poll/', views.poll_private, name='poll_private'),

    # Activity APIs
    path('api/activity/<str:activity_type>/join/',   views.join_activity,    name='join_activity'),
    path('api/activity/<str:activity_type>/leave/',  views.leave_activity,   name='leave_activity'),
    path('api/activity/<str:activity_type>/status/', views.activity_status,  name='activity_status'),

    # Legacy
    path('api/chat/messages/', views.get_chat_messages, name='get_chat_messages'),
    path('api/chat/send-legacy/', views.send_chat_message, name='send_chat_message'),
]
