from django.contrib import admin
from .models import QusetAnswer, SpiderBase, PSentiment, UserPermissionProfile, SystemPermission, FeatureAccessLog, UserProjectPermission, MobileAPIToken


@admin.register(SpiderBase)
class SpiderBaseAdmin(admin.ModelAdmin):
    list_display = ['id', 'IteamName', 'SalesChannel', 'IteamState', 'created_at']
    list_filter = ['SalesChannel', 'IteamState', 'created_at']
    search_fields = ['id', 'IteamName', 'SalesChannel']
    ordering = ['-created_at']


@admin.register(QusetAnswer)
class QusetAnswerAdmin(admin.ModelAdmin):
    list_display = ['comment_id', 'poiId', 'user_name', 'comment_grade', 'like_num', 'reply_num', 'release_time']
    list_filter = ['comment_grade', 'release_time']
    search_fields = ['comment_id', 'user_name', 'comment_content']
    ordering = ['-release_time']


@admin.register(PSentiment)
class PSentimentAdmin(admin.ModelAdmin):
    list_display = ['poiId', 'y_name', 'title', 'source_c', 'reply_num', 'p_time']
    list_filter = ['source_c', 'p_time']
    search_fields = ['poiId', 'y_name', 'title', 'source_c']
    ordering = ['-p_time']


@admin.register(UserPermissionProfile)
class UserPermissionProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'permission_level', 'can_view_advanced_sentiment', 'can_export_data', 'created_at']
    list_filter = ['permission_level', 'can_view_advanced_sentiment', 'can_export_data']
    search_fields = ['user__username', 'user__email']
    fieldsets = [
        ('基本信息', {
            'fields': ['user', 'permission_level']
        }),
        ('功能权限', {
            'fields': ['can_view_basic_sentiment', 'can_view_advanced_sentiment', 'can_export_data', 'can_manage_users', 'can_system_settings']
        }),
        ('平台限制', {
            'fields': ['allowed_platforms', 'forbidden_features']
        })
    ]


@admin.register(SystemPermission)
class SystemPermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']


@admin.register(FeatureAccessLog)
class FeatureAccessLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'feature_name', 'ip_address', 'access_time']
    list_filter = ['feature_name', 'access_time']
    search_fields = ['user__username', 'feature_name', 'ip_address']
    readonly_fields = ['user', 'feature_name', 'request_path', 'ip_address', 'user_agent', 'access_time']
    ordering = ['-access_time']


@admin.register(UserProjectPermission)
class UserProjectPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'project_name', 'platform', 'granted_by', 'granted_at', 'is_active']
    list_filter = ['platform', 'is_active', 'granted_at']
    search_fields = ['user__username', 'project_name', 'platform']
    readonly_fields = ['granted_at']
    ordering = ['-granted_at']


@admin.register(MobileAPIToken)
class MobileAPITokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'token_short', 'is_active', 'created_at', 'expires_at', 'last_used']
    list_filter = ['is_active', 'created_at', 'expires_at']
    search_fields = ['user__username', 'token']
    readonly_fields = ['token', 'created_at', 'last_used']
    ordering = ['-created_at']
    
    def token_short(self, obj):
        return f"{obj.token[:10]}..." if obj.token else ""
    token_short.short_description = 'Token'