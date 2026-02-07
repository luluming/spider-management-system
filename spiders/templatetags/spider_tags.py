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


@register.simple_tag
def url_if_exists(view_name):
    """安全解析URL，若不存在则返回空字符串，避免NoReverseMatch"""
    try:
        from django.urls import reverse
        return reverse(view_name)
    except Exception:
        return ''


@register.filter
def anomaly_labels(comment):
    """返回评论的异常类型标签列表（去重：1分时不重复显示差评）"""
    from django.utils import timezone
    labels = []
    if comment is None:
        return labels
    grade = getattr(comment, 'comment_grade', None)
    release_time = getattr(comment, 'release_time', None)
    now = timezone.now()
    current_year = now.year

    try:
        grade_num = float(grade) if grade is not None else None
    except (TypeError, ValueError):
        grade_num = None

    if grade_num is not None and (grade_num == 1 or grade_num == 1.0):
        labels.append('1分')
    elif grade_num is not None and grade_num <= 2:
        labels.append('差评')
    if release_time and (release_time.year > current_year or release_time > now):
        labels.append('时间异常')
    return labels


@register.filter
def anomaly_primary_category(comment):
    """返回评论的主异常分类（单一显示，便于分类查询）：时间异常 > 1分 > 差评"""
    labels = anomaly_labels(comment)
    if '时间异常' in labels:
        return '时间异常'
    if '1分' in labels:
        return '1分'
    if '差评' in labels:
        return '差评'
    return ''



