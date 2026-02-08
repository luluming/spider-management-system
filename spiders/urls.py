from django.urls import path
from . import views
from . import permission_views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('get-platform-monthly-trends/', views.get_platform_monthly_trends, name='get_platform_monthly_trends'),
    path('get-platform-project-daily-trends/', views.get_platform_project_daily_trends, name='get_platform_project_daily_trends'),
    path('comments/', views.comments_list, name='comments_list'),
    path('comment-anomaly-check/', views.comment_anomaly_check, name='comment_anomaly_check'),
    path('batch-update-comments/', views.batch_update_comments, name='batch_update_comments'),
    path('get-projects/', views.get_projects, name='get_projects'),
    path('get-statistics/', views.get_statistics, name='get_statistics'),
    path('export/', views.export_data, name='export_data'),
    path('sentiment-analysis/', views.sentiment_analysis, name='sentiment_analysis'),
    path('get-sentiment-statistics/', views.get_sentiment_statistics, name='get_sentiment_statistics'),
    path('get-monthly-trend-data/', views.get_monthly_trend_data, name='get_monthly_trend_data'),
    path('get-platform-project-trends/', views.get_platform_project_trends, name='get_platform_project_trends'),
    path('platform-statistics/', views.platform_statistics, name='platform_statistics'),
    path('get-sentiment-analytics/', views.get_sentiment_analytics, name='get_sentiment_analytics'),
    # 数据管理模块
    path('data-management/', views.data_management, name='data_management'),
    path('add-spider/', views.add_spider, name='add_spider'),
    path('edit-spider/<int:spider_id>/', views.edit_spider, name='edit_spider'),
    path('delete-spider/<int:spider_id>/', views.delete_spider, name='delete_spider'),
    path('get-spider-detail/<int:spider_id>/', views.get_spider_detail, name='get_spider_detail'),
    # 用户管理模块
    path('user-management/', views.user_management, name='user_management'),
    path('add-user/', views.add_user, name='add_user'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('get-user-detail/<int:user_id>/', views.get_user_detail, name='get_user_detail'),
    path('user-project-permissions/<int:user_id>/', views.user_project_permissions, name='user_project_permissions'),
    path('assign-project-permission/', views.assign_project_permission, name='assign_project_permission'),
    path('revoke-project-permission/<int:permission_id>/', views.revoke_project_permission, name='revoke_project_permission'),
    path('get-platform-projects/', views.get_platform_projects, name='get_platform_projects'),
    # 手机APP API接口
    path('api/mobile/login/', views.mobile_api_login, name='mobile_api_login'),
    path('api/mobile/user-projects/', views.mobile_api_user_projects, name='mobile_api_user_projects'),
    path('add-comment/', views.add_comment, name='add_comment'),
    path('get-comment-detail/<str:comment_id>/', views.get_comment_detail, name='get_comment_detail'),
    path('edit-comment/<str:comment_id>/', views.edit_comment, name='edit_comment'),
    path('delete-comment/<str:comment_id>/', views.delete_comment, name='delete_comment'),
    path('get-platform-data/', views.get_platform_data, name='get_platform_data'),
    path('get-projects-by-platform/', views.get_projects_by_platform, name='get_projects_by_platform'),
    # 权限管理模块
    path('permission-management/', permission_views.permission_management, name='permission_management'),
    path('edit-permission/<int:user_id>/', permission_views.edit_user_permission, name='edit_user_permission'),
    path('permission-log/', permission_views.permission_access_log, name='permission_access_log'),
    path('permission-stats/', permission_views.permission_stats, name='permission_stats'),
    path('bulk-permission-update/', permission_views.bulk_permission_update, name='bulk_permission_update'),
    path('create-permission-template/', permission_views.create_permission_template, name='create_permission_template'),
    path('check-user-permission/', permission_views.check_user_permission_api, name='check_user_permission_api'),
    # 基础表查询模块
    path('basic-table-query/', views.basic_table_query, name='basic_table_query'),
    path('add-sentiment-record/', views.add_sentiment_record, name='add_sentiment_record'),
    path('edit-sentiment-record/<path:poi_id>/', views.edit_sentiment_record, name='edit_sentiment_record'),
    path('update-sentiment-record/', views.update_sentiment_record, name='update_sentiment_record'),
    path('delete-sentiment-record/<path:poi_id>/', views.delete_sentiment_record, name='delete_sentiment_record'),
    path('get-sentiment-record-detail/<path:poi_id>/', views.get_sentiment_record_detail, name='get_sentiment_record_detail'),
    path('get-sentiment-record-for-edit/', views.get_sentiment_record_for_edit, name='get_sentiment_record_for_edit'),
    path('export-sentiment-data/', views.export_sentiment_data, name='export_sentiment_data'),
]

