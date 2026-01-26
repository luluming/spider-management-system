from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.models import User
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from .models import UserPermissionProfile, SystemPermission, FeatureAccessLog
from .decorators import require_permission, permission_required_or_json, log_access

@user_passes_test(lambda u: u.is_superuser)
@log_access('permission_management')
def permission_management(request):
    """权限管理页面"""
    
    # 获取权限列表
    profiles = UserPermissionProfile.objects.select_related('user').all()
    
    # 搜索功能
    search_query = request.GET.get('search', '')
    if search_query:
        profiles = profiles.filter(user__username__icontains=search_query)
    
    # 按权限级别过滤
    filter_level = request.GET.get('level', '')
    if filter_level:
        profiles = profiles.filter(permission_level=filter_level)
    
    # 分页
    paginator = Paginator(profiles, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'filter_level': filter_level,
        'level_choices': UserPermissionProfile.PERMISSION_LEVEL_CHOICES,
    }
    
    return render(request, 'spiders/simple_permission.html', context)


@require_permission('manage_users')
@log_access('edit_user_permission')
def edit_user_permission(request, user_id):
    """编辑用户权限"""
    user_obj = get_object_or_404(User, id=user_id)
    profile, created = UserPermissionProfile.objects.get_or_create(
        user=user_obj,
        defaults={'permission_level': 'basic'}
    )
    
    if request.method == 'POST':
        # 更新权限配置
        profile.permission_level = request.POST.get('permission_level')
        profile.can_view_basic_sentiment = 'can_view_basic_sentiment' in request.POST
        profile.can_view_advanced_sentiment = 'can_view_advanced_sentiment' in request.POST
        profile.can_export_data = 'can_export_data' in request.POST
        profile.can_manage_users = 'can_manage_users' in request.POST
        profile.can_system_settings = 'can_system_settings' in request.POST
        
        # 处理平台限制
        allowed_platforms = request.POST.getlist('allowed_platforms')
        profile.allowed_platforms = allowed_platforms
        
        # 处理功能禁止
        forbidden_features = request.POST.getlist('forbidden_features')
        profile.forbidden_features = forbidden_features
        
        profile.save()
        
        messages.success(request, f'用户 {user_obj.username} 的权限配置已更新')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': '权限更新成功'})
        
        return redirect('permission_management')
    
    # 获取可用的平台列表
    from .models import PSentiment
    available_platforms = list(PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c=''))
    
    context = {
        'user_obj': user_obj,
        'profile': profile,
        'level_choices': UserPermissionProfile.PERMISSION_LEVEL_CHOICES,
        'available_platforms': available_platforms,
    }
    
    return render(request, 'spiders/edit_permission.html', context)


@require_permission('manage_users')
@log_access('permission_access_log')
def permission_access_log(request):
    """权限访问日志"""
    
    logs = FeatureAccessLog.objects.select_related('user').all()
    
    # 时间过滤
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    if start_date:
        logs = logs.filter(access_time__date__gte=start_date)
    if end_date:
        logs = logs.filter(access_time__date__lte=end_date)
    
    # 功能过滤
    feature_filter = request.GET.get('feature', '')
    if feature_filter:
        logs = logs.filter(feature_name__icontains=feature_filter)
    
    # 用户过滤
    user_filter = request.GET.get('user', '')
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)
    
    # 分页
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'start_date': start_date,
        'end_date': end_date,
        'feature_filter': feature_filter,
        'user_filter': user_filter,
    }
    
    return render(request, 'spiders/permission_log.html', context)


@require_permission('manage_users')
def permission_stats(request):
    """权限统计"""
    
    # 用户权限统计
    permission_stats_data = []
    for level_code, level_name in UserPermissionProfile.PERMISSION_LEVEL_CHOICES:
        count = UserPermissionProfile.objects.filter(permission_level=level_code).count()
        permission_stats_data.append({
            'level': level_name,
            'count': count
        })
    
    # 功能访问统计（最近30天）
    from datetime import datetime, timedelta
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    feature_access_stats = FeatureAccessLog.objects.filter(
        access_time__gte=thirty_days_ago
    ).values('feature_name').extra(
        select={'access_count': 'COUNT(*)'}
    ).values('feature_name').extra(
        select={'access_count': 'COUNT(*)', 'latest_access': 'MAX(access_time)'}
    ).order_by('-access_count')
    
    # 活跃用户统计
    active_users = FeatureAccessLog.objects.filter(
        access_time__gte=thirty_days_ago
    ).values('user__username').extra(
        select={'access_count': 'COUNT(*)'}
    ).order_by('-access_count')[:10]
    
    context = {
        'permission_stats': permission_stats_data,
        'feature_stats': feature_access_stats,
        'active_users': active_users,
    }
    
    return render(request, 'spiders/permission_stats.html', context)


@require_permission('manage_users')
def bulk_permission_update(request):
    """批量权限更新"""
    if request.method == 'POST':
        try:
            action = request.POST.get('action')
            user_ids = request.POST.getlist('user_ids')
            
            if not user_ids:
                return JsonResponse({'success': False, 'message': '请选择要操作的用户'})
            
            if action == 'promote_to_analyst':
                UserPermissionProfile.objects.filter(user_id__in=user_ids).update(
                    permission_level='analyst',
                    can_view_basic_sentiment=True,
                    can_view_advanced_sentiment=False
                )
                message = f'成功将 {len(user_ids)} 个用户提升为分析师'
            
            elif action == 'promote_to_senior':
                UserPermissionProfile.objects.filter(user_id__in=user_ids).update(
                    permission_level='senior_analyst',
                    can_view_basic_sentiment=True,
                    can_view_advanced_sentiment=True,
                    can_export_data=True
                )
                message = f'成功将 {len(user_ids)} 个用户提升为高级分析师'
            
            elif action == 'restrict_to_basic':
                UserPermissionProfile.objects.filter(user_id__in=user_ids).update(
                    permission_level='basic',
                    can_view_basic_sentiment=True,
                    can_view_advanced_sentiment=False,
                    can_export_data=False
                )
                message = f'成功将 {len(user_ids)} 个用户限制为基础用户'
            
            else:
                return JsonResponse({'success': False, 'message': '无效的操作'})
            
            return JsonResponse({'success': True, 'message': message})
        
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'操作失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '仅支持POST请求'})


@require_permission('manage_users')
def create_permission_template(request):
    """创建权限模板"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description')
            
            if not name:
                return JsonResponse({'success': False, 'message': '模板名称不能为空'})
            
            template = SystemPermission.objects.create(
                name=name,
                description=description,
                can_view_basic_sentiment='can_view_basic_sentiment' in request.POST,
                can_view_advanced_sentiment='can_view_advanced_sentiment' in request.POST,
                can_export_data='can_export_data' in request.POST,
                can_manage_users='can_manage_users' in request.POST,
                can_system_settings='can_system_settings' in request.POST
            )
            
            return JsonResponse({'success': True, 'message': '权限模板创建成功', 'template_id': template.id})
        
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'创建失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '仅支持POST请求'})


def check_user_permission_api(request):
    """检查用户权限的API"""
    if not request.user.is_authenticated:
        return JsonResponse({'authenticated': False})
    
    try:
        profile = request.user.permission_profile
        return JsonResponse({
            'authenticated': True,
            'permission_level': profile.permission_level,
            'permissions': {
                'can_view_basic_sentiment': profile.can_view_basic_sentiment,
                'can_view_advanced_sentiment': profile.can_view_advanced_sentiment,
                'can_export_data': profile.can_export_data,
                'can_manage_users': profile.can_manage_users,
                'can_system_settings': profile.can_system_settings,
            },
            'allowed_platforms': profile.allowed_platforms,
            'forbidden_features': profile.forbidden_features,
        })
    except UserPermissionProfile.DoesNotExist:
        return JsonResponse({
            'authenticated': True,
            'permission_level': 'basic',
            'permissions': {
                'can_view_basic_sentiment': True,
                'can_view_advanced_sentiment': False,
                'can_export_data': False,
                'can_manage_users': False,
                'can_system_settings': False,
            },
            'allowed_platforms': [],
            'forbidden_features': [],
        })



