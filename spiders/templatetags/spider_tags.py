from django import template

register = template.Library()

@register.filter
def can_view_advanced(user):
    """检查用户可以查看高级分析功能"""
    if not user or not user.is_authenticated:
        return False
    try:
        return user.permission_profile.can_view_advanced_sentiment
    except:
        return False

@register.filter
def can_export_data(user):
    """检查用户可以导出数据"""
    if not user or not user.is_authenticated:
        return False
    try:
        return user.permission_profile.can_export_data
    except:
        return False

@register.filter
def can_manage_users(user):
    """检查用户可以管理用户"""
    if not user or not user.is_authenticated:
        return False
    try:
        return user.permission_profile.can_manage_users
    except:
        return False



