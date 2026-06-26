from django.urls import path
from . import views

urlpatterns = [
    # Pages
    path('', views.landing, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('history/', views.expense_history, name='history'),
    path('analytics/', views.analytics_page, name='analytics'),
    path('budget/', views.budget_planner, name='budget_planner'),
    path('settings/', views.settings_page, name='settings'),
    path('settings/security/', views.security_settings, name='security_settings'),
    path('settings/security/revoke/<int:session_id>/', views.revoke_device_session, name='revoke_device_session'),
    path('profile/', views.profile_page, name='profile'),
    path('admin-dashboard/', views.custom_admin_dashboard, name='admin_dashboard'),
    
    # AJAX APIS
    path('api/parse-voice/', views.parse_voice, name='parse_voice'),
    path('api/chatbot/', views.chatbot_query, name='chatbot_query'),
    path('api/expense/add/', views.add_expense_ajax, name='add_expense_ajax'),
    path('api/expense/edit/', views.edit_expense_ajax, name='edit_expense_ajax'),
    path('api/expense/delete/', views.delete_expense_ajax, name='delete_expense_ajax'),
    path('api/budget/edit/', views.edit_budget_ajax, name='edit_budget_ajax'),
    path('api/budget/delete/', views.delete_budget_ajax, name='delete_budget_ajax'),
    path('api/whatsapp/webhook/', views.whatsapp_webhook, name='whatsapp_webhook'),
    path('api/admin/toggle-user/', views.admin_toggle_user, name='admin_toggle_user'),
    path('api/admin/change-role/', views.admin_change_role, name='admin_change_role'),
    path('api/admin/change-subscription/', views.admin_change_subscription, name='admin_change_subscription'),
    path('api/admin/resolve-ticket/', views.admin_resolve_ticket, name='admin_resolve_ticket'),
    path('api/admin/broadcast/', views.admin_broadcast_notification, name='admin_broadcast_notification'),
    
    # Exports
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),   
    path(
    'send-whatsapp/',
    views.send_whatsapp_to_user,
    name='send_whatsapp'
),
    path('service-worker.js', views.service_worker, name='service_worker'),

    # Marketing pages
    path('about/', views.about_view, name='about'),
    path('features/', views.features_view, name='features'),
    path('pricing/', views.pricing_view, name='pricing'),
    path('contact/', views.contact_view, name='contact'),

    # Gamification & subscriptions
    path('achievements/', views.achievements_view, name='achievements'),
    path('referral/', views.referral_view, name='referral'),
    path('api/upgrade/', views.upgrade_subscription, name='upgrade_subscription'),
    path('checkout/', views.checkout_view, name='checkout'),
    path('api/coupon/validate/', views.validate_coupon_ajax, name='validate_coupon_ajax'),
    path('api/gdpr/export/', views.gdpr_export_data, name='gdpr_export_data'),
    path('api/gdpr/delete/', views.gdpr_delete_account, name='gdpr_delete_account'),
    path('api/challenge/create/', views.create_challenge, name='create_challenge'),
    path('api/notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),

    # SMS Bank Parser
    path('api/expense/parse-sms/', views.parse_sms_ajax, name='parse_sms_ajax'),

    # Phase 2 Revenue & Support Additions
    path('team/', views.team_management, name='team_management'),
    path('api/team/add/', views.add_team_member_ajax, name='add_team_member_ajax'),
    path('api/team/remove/', views.remove_team_member_ajax, name='remove_team_member_ajax'),
    path('offers/', views.affiliate_offers, name='affiliate_offers'),
    path('support/', views.support_page, name='support_page'),
    path('api/expense/sync/', views.sync_offline_expenses, name='sync_offline_expenses'),
    path('otp/', views.otp_verify, name='otp_verify'),
    
    # Phase 4 Additions
    path('api/team/change-role/', views.change_member_role_ajax, name='change_member_role_ajax'),
    path('api/team/submit-expense/', views.submit_team_expense_ajax, name='submit_team_expense_ajax'),
    path('api/team/process-expense/', views.process_team_expense_ajax, name='process_team_expense_ajax'),
    
    path('marketplace/', views.marketplace_view, name='marketplace'),
    path('mobile-preview/', views.mobile_preview_view, name='mobile_preview'),
    
    path('forum/', views.forum_view, name='forum_page'),
    path('forum/post/<int:post_id>/', views.forum_detail_view, name='forum_detail'),
    path('api/forum/post/create/', views.create_forum_post_ajax, name='create_forum_post_ajax'),
    path('api/forum/post/upvote/', views.upvote_forum_post_ajax, name='upvote_forum_post_ajax'),
    path('api/forum/comment/create/', views.create_forum_comment_ajax, name='create_forum_comment_ajax'),
    path('api/forum/post/report/', views.report_forum_post_ajax, name='report_forum_post_ajax'),
    path('api/marketplace/order/', views.create_marketplace_order_ajax, name='create_marketplace_order_ajax'),
    path('offers/redirect/<int:offer_id>/', views.offer_redirect, name='offer_redirect'),
    path('api/offers/conversion/', views.record_offer_conversion_api, name='record_offer_conversion_api'),
    
    path('export/excel/', views.export_excel, name='export_excel'),
    
    # Marketing Blog & SEO
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('sitemap.xml', views.sitemap_view, name='sitemap_view'),
    path('robots.txt', views.robots_view, name='robots_view'),
    
    # Developer API keys
    path('developer/keys/', views.developer_keys_view, name='developer_keys'),
    path('api/developer/keys/create/', views.create_developer_key_ajax, name='create_developer_key_ajax'),
    path('api/developer/keys/revoke/', views.revoke_developer_key_ajax, name='revoke_developer_key_ajax'),
    path('metrics/', views.prometheus_metrics, name='prometheus_metrics'),
]

