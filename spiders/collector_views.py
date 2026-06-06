import json

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from datetime import timedelta

from accounts.models import OperationLog
from accounts.views import get_client_ip
from spiders.models import (
    AppCollector,
    AppDeviceRebindRequest,
    AppProjectPermission,
    PSentiment,
)
from spiders.mobile.utils import normalize_device_id


def staff_required(view):
    return login_required(user_passes_test(lambda u: u.is_staff)(view))


def _collector_page_context(**extra):
    ctx = {
        'pending_rebind_count': AppDeviceRebindRequest.objects.filter(
            status__in=AppDeviceRebindRequest.ADMIN_PENDING_STATUSES,
        ).count(),
    }
    ctx.update(extra)
    return ctx


def redirect_collector_permissions(request, collector_id):
    from django.shortcuts import redirect
    return redirect('app_collector_permissions', collector_id=collector_id)


@staff_required
def app_collector_management(request):
    collectors = AppCollector.objects.all().order_by('-created_at')
    return render(request, 'spiders/app_collector_management.html', _collector_page_context(collectors=collectors))


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_collector_add(request):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'JSON 格式错误'})

    username = str(data.get('username', '')).strip()
    password = data.get('password', '')
    display_name = str(data.get('display_name', '') or '').strip()
    phone = str(data.get('phone', '') or '').strip()
    if not username or not password:
        return JsonResponse({'success': False, 'message': '用户名和密码不能为空'})
    if AppCollector.objects.filter(username=username).exists():
        return JsonResponse({'success': False, 'message': '用户名已存在'})

    collector = AppCollector(
        username=username,
        display_name=display_name,
        phone=phone,
        created_by=request.user,
    )
    collector.set_password(password)
    collector.save()
    OperationLog.objects.create(
        user=request.user,
        operation='创建App采集员',
        action='create',
        description=f'创建App采集员: {username}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return JsonResponse({'success': True, 'message': '创建成功', 'id': collector.id})


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_collector_edit(request, collector_id):
    collector = get_object_or_404(AppCollector, id=collector_id)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'JSON 格式错误'})

    if 'display_name' in data:
        collector.display_name = str(data.get('display_name') or '').strip()
    if 'phone' in data:
        collector.phone = str(data.get('phone') or '').strip()
    if 'is_active' in data:
        collector.is_active = bool(data.get('is_active'))
    password = data.get('password')
    if password:
        if len(password) < 6:
            return JsonResponse({'success': False, 'message': '密码长度至少6位'})
        collector.set_password(password)
    collector.save()
    OperationLog.objects.create(
        user=request.user,
        operation='修改App采集员',
        action='update',
        description=f'修改App采集员信息: {collector.username}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return JsonResponse({'success': True, 'message': '更新成功'})


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_collector_reset_password(request, collector_id):
    """重置采集员登录密码"""
    collector = get_object_or_404(AppCollector, id=collector_id)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'JSON 格式错误'})

    password = data.get('password', '')
    confirm = data.get('confirm_password', '')
    if not password:
        return JsonResponse({'success': False, 'message': '新密码不能为空'})
    if len(password) < 6:
        return JsonResponse({'success': False, 'message': '密码长度至少6位'})
    if password != confirm:
        return JsonResponse({'success': False, 'message': '两次输入的密码不一致'})

    collector.set_password(password)
    collector.reset_login_failures()
    collector.save()
    OperationLog.objects.create(
        user=request.user,
        operation='重置App采集员密码',
        action='update',
        description=f'重置App采集员密码: {collector.username}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return JsonResponse({'success': True, 'message': f'已重置 {collector.username} 的登录密码'})


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_collector_unlock(request, collector_id):
    collector = get_object_or_404(AppCollector, id=collector_id)
    collector.reset_login_failures()
    return JsonResponse({'success': True, 'message': '账号已解锁'})


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_collector_unbind_device(request, collector_id):
    collector = get_object_or_404(AppCollector, id=collector_id)
    collector.clear_device_binding()
    OperationLog.objects.create(
        user=request.user,
        operation='解绑App采集员设备',
        action='update',
        description=f'清除设备绑定: {collector.username}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return JsonResponse({'success': True, 'message': '设备绑定已清除'})


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_collector_bind_device(request, collector_id):
    """管理员手动绑定/更换设备"""
    collector = get_object_or_404(AppCollector, id=collector_id)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'JSON 格式错误'})

    device_id = normalize_device_id(data.get('device_id', ''))
    device_info = str(data.get('device_info', '') or '').strip()
    if not device_id:
        return JsonResponse({'success': False, 'message': '设备 ID 不能为空'})

    collector.bind_device(device_id, device_info)
    AppDeviceRebindRequest.objects.filter(
        collector=collector,
        status__in=AppDeviceRebindRequest.ADMIN_PENDING_STATUSES,
    ).update(status=AppDeviceRebindRequest.STATUS_CANCELLED)

    OperationLog.objects.create(
        user=request.user,
        operation='绑定App采集员设备',
        action='update',
        description=f'绑定设备 {device_id}: {collector.username}',
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return JsonResponse({
        'success': True,
        'message': '设备绑定成功',
        'device_id': collector.bound_device_id,
        'device_info': collector.bound_device_info,
    })


@staff_required
def app_collector_permissions(request, collector_id):
    collector = get_object_or_404(AppCollector, id=collector_id)
    permissions = AppProjectPermission.objects.filter(collector=collector).order_by('-granted_at')
    platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().order_by('source_c')
    platforms = [p for p in platforms if p]
    return render(request, 'spiders/app_collector_permissions.html', _collector_page_context(
        collector=collector,
        permissions=permissions,
        active_permission_count=permissions.filter(is_active=True).count(),
        platforms=platforms,
    ))


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_assign_permission(request):
    try:
        data = json.loads(request.body.decode('utf-8') or '{}') if request.content_type == 'application/json' else request.POST
    except json.JSONDecodeError:
        data = request.POST

    collector_id = data.get('collector_id')
    poi_ids = data.get('poi_ids') or []
    poi_id = data.get('poi_id')
    notes = str(data.get('notes', '') or '')

    if poi_id and not poi_ids:
        poi_ids = [poi_id]
    if isinstance(poi_ids, str):
        poi_ids = [x.strip() for x in poi_ids.split(',') if x.strip()]

    if not collector_id or not poi_ids:
        return JsonResponse({'success': False, 'message': 'collector_id 和 poi_id(s) 为必填'})

    collector = get_object_or_404(AppCollector, id=collector_id)
    created = 0
    skipped = 0
    assigned = []
    for pid in poi_ids:
        try:
            project = PSentiment.objects.get(poiId=str(pid))
        except PSentiment.DoesNotExist:
            skipped += 1
            continue
        item_name = (project.itemName or project.title or str(pid)).strip()
        perm, was_created = AppProjectPermission.objects.update_or_create(
            collector=collector,
            poi_id=str(project.poiId),
            defaults={
                'item_name': item_name,
                'platform': project.source_c or '',
                'is_active': True,
                'granted_by': request.user,
                'notes': notes,
            },
        )
        if was_created:
            created += 1
        else:
            skipped += 1
        assigned.append({
            'id': perm.id,
            'item_name': perm.item_name,
            'platform': perm.platform,
            'poi_id': perm.poi_id,
            'granted_at': timezone.localtime(perm.granted_at).strftime('%Y-%m-%d %H:%M'),
            'is_active': perm.is_active,
        })
    return JsonResponse({
        'success': True,
        'message': f'分配完成：新增/更新 {created} 条，跳过 {skipped} 条',
        'permissions': assigned,
    })


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_revoke_permission(request, permission_id):
    perm = get_object_or_404(AppProjectPermission, id=permission_id)
    perm.is_active = False
    perm.save(update_fields=['is_active'])
    return JsonResponse({'success': True, 'message': '权限已撤销'})


@staff_required
@require_http_methods(['GET'])
def app_platform_projects(request):
    platform = request.GET.get('platform', '').strip()
    if not platform:
        return JsonResponse({'success': False, 'message': 'platform 为必填'})
    projects = PSentiment.objects.filter(source_c=platform).order_by('itemName', 'poiId')
    data = []
    for p in projects:
        data.append({
            'poiId': str(p.poiId),
            'itemName': (p.itemName or p.title or str(p.poiId)).strip(),
            'platform': p.source_c or '',
        })
    return JsonResponse({'success': True, 'projects': data})


@staff_required
def app_device_rebind_list(request):
    status = request.GET.get('status', 'pending')
    reqs = AppDeviceRebindRequest.objects.select_related('collector', 'reviewed_by').order_by('-created_at')
    if status == 'pending':
        reqs = reqs.filter(status__in=AppDeviceRebindRequest.ADMIN_PENDING_STATUSES)
    elif status and status != 'all':
        reqs = reqs.filter(status=status)
    return render(request, 'spiders/app_device_rebind_list.html', _collector_page_context(
        requests=reqs[:200],
        current_status=status,
        status_choices=AppDeviceRebindRequest.STATUS_CHOICES,
    ))


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_device_rebind_approve(request, request_id):
    req = get_object_or_404(AppDeviceRebindRequest.objects.select_related('collector'), id=request_id)
    if req.status not in AppDeviceRebindRequest.ADMIN_PENDING_STATUSES:
        return JsonResponse({'success': False, 'message': '当前状态不可审批'})

    collector = req.collector
    collector.bind_device(req.new_device_id, req.new_device_info)
    collector.reset_login_failures()

    req.status = AppDeviceRebindRequest.STATUS_COMPLETED
    req.reviewed_by = request.user
    req.reviewed_at = timezone.now()
    req.completed_at = timezone.now()
    req.approved_expires_at = timezone.now()
    req.save()

    OperationLog.objects.create(
        user=request.user,
        operation='审批App设备注册/换绑',
        action='update',
        description=(
            f'已批准并绑定设备 {req.new_device_id} → 采集员 {collector.username} '
            f'（单号 {req.request_no}）'
        ),
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
    )
    return JsonResponse({
        'success': True,
        'message': f'已批准，设备已绑定到账号「{collector.username}」，App 可直接登录',
        'collector_id': collector.id,
        'device_id': collector.bound_device_id,
    })


@staff_required
@csrf_exempt
@require_http_methods(['POST'])
def app_device_rebind_reject(request, request_id):
    req = get_object_or_404(AppDeviceRebindRequest, id=request_id)
    if req.status not in AppDeviceRebindRequest.ADMIN_PENDING_STATUSES:
        return JsonResponse({'success': False, 'message': '当前状态不可审批'})
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        data = request.POST
    reason = str(data.get('reject_reason', '') or '管理员拒绝')
    req.status = AppDeviceRebindRequest.STATUS_REJECTED
    req.reviewed_by = request.user
    req.reviewed_at = timezone.now()
    req.reject_reason = reason
    req.save()
    return JsonResponse({'success': True, 'message': '已拒绝'})
