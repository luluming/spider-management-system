from django.contrib import admin
from .models import UserProfile, OperationLog


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'department', 'phone', 'created_at']
    list_filter = ['role', 'department', 'created_at']
    search_fields = ['user__username', 'user__email', 'department', 'phone']
    ordering = ['-created_at']


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'description', 'ip_address', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__username', 'description', 'ip_address']
    ordering = ['-created_at']
    readonly_fields = ['created_at']