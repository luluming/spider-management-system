from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
import json

def require_permission(permission_name):
    """
    权限控制装饰器
    
    参数:
    - permission_name: 所需权限名称
    
    用法:
    @require_permission('sentiment_analysis_advanced')
    def advanced_analysis(request):
        return render(request, 'advanced.html')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 首先检查用户是否已登录
            if not request.user.is_authenticated:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': '请先登录'}, status=401)
                return redirect('accounts:login')
            
            # 超级用户拥有所有权限
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # 检查权限配置
            try:
                profile = request.user.permission_profile
                
                if not profile.can_access_feature(permission_name):
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                        return JsonResponse({
                            'error': '权限不足',
                            'message': f'您没有访问{permission_name}功能的权限，请联系管理员'
                        }, status=403)
                    
                    messages.error(request, f'权限不足：您没有访问{permission_name}功能的权限')
                    return redirect('dashboard')
                
            except UserPermissionProfile.DoesNotExist:
                # 如果没有权限配置，创建基础配置
                from spiders.models import UserPermissionProfile
                UserPermissionProfile.objects.create(
                    user=request.user,
                    permission_level='basic'
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': '权限配置未完成',
                        'message': '您的权限配置尚未完成，请联系管理员'
                    }, status=403)
                
                messages.warning(request, '您的权限配置尚未完成，请联系管理员')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def require_permission_level(level):
    """
    基于权限级别的装饰器
    
    参数:
    - level: 所需权限级别 ('basic', 'analyst', 'senior_analyst', 'admin', 'super_admin')
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            try:
                profile = request.user.permission_profile
                level_hierarchy = {
                    'basic': 1,
                    'analyst': 2,
                    'senior_analyst': 3,
                    'admin': 4,
                    'super_admin': 5
                }
                
                required_level = level_hierarchy.get(level, 1)
                user_level = level_hierarchy.get(profile.permission_level, 1)
                
                if user_level < required_level:
                    messages.error(request, f'权限不足：需要{level}级别权限')
                    return redirect('dashboard')
                
            except UserPermissionProfile.DoesNotExist:
                messages.warning(request, '权限配置异常，请联系管理员')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator


def log_access(feature_name=None):
    """
    访问日志记录装饰器
    
    参数:
    - feature_name: 功能名称，如果不提供将从函数名推断
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 执行视图函数
            response = view_func(request, *args, **kwargs)
            
            # 记录访问日志
            if request.user.is_authenticated:
                from spiders.models import FeatureAccessLog
                
                log_feature = feature_name or view_func.__name__
                
                # 获取客户端IP
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip = x_forwarded_for.split(',')[0]
                else:
                    ip = request.META.get('REMOTE_ADDR')
                
                # 创建访问日志
                FeatureAccessLog.objects.create(
                    user=request.user,
                    feature_name=log_feature,
                    request_path=request.path,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            
            return response
        
        return _wrapped_view
    return decorator


def permission_required_or_json(permission_names, error_message="权限不足"):
    """
    权限检查装饰器，AJAX请求返回JSON，普通请求返回HTTP 403
    
    参数:
    - permission_names: 权限名称列表或单个权限名称
    - error_message: 错误消息
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'error': '请先登录'}, status=401)
                return redirect('accounts:login')
            
            if not isinstance(permission_names, list):
                permissions = [permission_names]
            else:
                permissions = permission_names
            
            # 检查是否拥有任一权限
            has_permission = False
            if request.user.is_superuser:
                has_permission = True
            else:
                try:
                    profile = request.user.permission_profile
                    has_permission = any(profile.can_access_feature(perm) for perm in permissions)
                except UserPermissionProfile.DoesNotExist:
                    has_permission = False
            
            if not has_permission:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': error_message,
                        'message': f'您没有访问以下功能的权限: {", ".join(permissions)}'
                    }, status=403)
                
                raise PermissionDenied(error_message)
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator



