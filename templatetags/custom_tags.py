from django import template
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

register = template.Library()

@register.filter
def has_permission(user, permission_name):
    """
    检查用户是否有特定权限
    
    参数:
    - user: 用户对象
    - permission_name: 权限名称字符串
    
    返回: True/False
    """
    if not user or not user.is_authenticated:
        return False
    
    # 超级用户拥有所有权限
    if user.is_superuser:
        return True
    
    # 检查实际权限
    return user.has_perm(permission_name)

@register.filter
def in_group(user, group_name):
    """
    检查用户是否属于特定用户组
    
    参数:
    - user: 用户对象
    - group_name: 用户组名称
    
    返回: True/False
    """
    if not user or not user.is_authenticated:
        return False
    
    return user.groups.filter(name=group_name).exists()

@register.filter
def can_access_feature(user, feature):
    """
    检查用户是否可以访问特定功能
    
    参数:
    - user: 用户对象
    - feature: 功能名称
    
    返回: True/False
    """
    if not user or not user.is_authenticated:
        return False
    
    # 预定义的功能访问权限映射
    feature_permissions = {
        'sentiment_analysis_advanced': 'sentiment_analysis.view_advanced',
        'export_data': 'spiders.export_data',
        'manage_users': 'auth.manage_users',
        'system_settings': 'spiders.system_settings'
    }
    
    permission = feature_permissions.get(feature)
    if not permission:
        return False
    
    if user.is_superuser:
        return True
    
    return user.has_perm(permission)

@register.simple_tag
def get_user_role(user):
    """
    获取用户的角色描述
    
    参数:
    - user: 用户对象
    
    返回: 角色描述字符串
    """
    if not user or not user.is_authenticated:
        return "游客"
    
    if user.is_superuser:
        return "超级管理员"
    
    if user.is_staff:
        return "系统管理员"
    
    # 根据权限判断角色
    if user.has_perm('sentiment_analysis.view_advanced'):
        return "高级情感分析师"
    elif user.has_perm('sentiment_analysis.view_basic'):
        return "情感分析师"
    else:
        return "普通用户"



