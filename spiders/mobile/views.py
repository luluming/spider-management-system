import json

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from datetime import timedelta

from django.conf import settings

from spiders.models import (
    AppDeviceRebindRequest,
    AppProjectPermission,
    QusetAnswer,
    AppCommentSubmission,
    AppCollector,
    AppAPIToken,
)
from spiders.mobile.utils import (
    active_rebind_request,
    api_response,
    authenticate_collector,
    build_comment_payload,
    expire_rebind_if_needed,
    generate_captcha_image,
    generate_request_no,
    generate_verify_code,
    get_client_ip,
    get_device_id,
    hash_verify_code,
    issue_token,
    collector_has_poi,
    parse_json,
    save_comment_for_collector,
    serialize_comment,
    store_captcha,
    today_range,
    verify_captcha,
)


def _require_collector(request):
    collector, api_token = authenticate_collector(request)
    if not collector:
        return None, None, api_response(False, '无效或已过期的 Token', status=401)
    if not collector.is_active:
        return None, None, api_response(False, '账号已禁用', status=403)
    return collector, api_token, None


@csrf_exempt
@require_http_methods(['GET'])
def mobile_captcha(request):
    captcha_text, captcha_img = generate_captcha_image()
    captcha_id = store_captcha(captcha_text)
    return api_response(True, 'ok', {
        'captcha_id': captcha_id,
        'captcha_image': captcha_img,
        'expires_in': 300,
    })


@csrf_exempt
@require_http_methods(['POST'])
def mobile_login(request):
    try:
        data = parse_json(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    username = str(data.get('username', '')).strip()
    password = data.get('password', '')
    device_id = get_device_id(request, data)
    device_info = str(data.get('device_info', '') or '')
    captcha_id = data.get('captcha_id', '')
    captcha_code = data.get('captcha_code', '')

    if not all([username, password, device_id, captcha_id, captcha_code]):
        return api_response(False, 'username、password、device_id、captcha_id、captcha_code 均为必填', status=400)
    if not verify_captcha(captcha_id, captcha_code):
        return api_response(False, '验证码错误或已过期', status=400)

    try:
        collector = AppCollector.objects.get(username=username)
    except AppCollector.DoesNotExist:
        return api_response(False, '用户名或密码错误', status=401)

    if not collector.is_active:
        return api_response(False, '账号已禁用', status=403)
    if collector.is_locked():
        locked_until = timezone.localtime(collector.locked_until).strftime('%Y-%m-%d %H:%M:%S')
        return api_response(False, f'账号已锁定，请 {locked_until} 后再试', status=423)

    if not collector.check_password(password):
        collector.record_failed_login()
        return api_response(False, '用户名或密码错误', status=401)

    approved_req = AppDeviceRebindRequest.objects.filter(
        collector=collector,
        status=AppDeviceRebindRequest.STATUS_APPROVED,
        new_device_id=device_id,
    ).order_by('-reviewed_at').first()
    if approved_req:
        expire_rebind_if_needed(approved_req)
        if approved_req.status == AppDeviceRebindRequest.STATUS_APPROVED:
            collector.bind_device(device_id, device_info)
            collector.reset_login_failures()
            collector.last_login_at = timezone.now()
            collector.last_login_ip = get_client_ip(request)
            collector.save(update_fields=['last_login_at', 'last_login_ip', 'updated_at'])
            api_token = issue_token(collector, device_id)
            approved_req.status = AppDeviceRebindRequest.STATUS_COMPLETED
            approved_req.completed_at = timezone.now()
            approved_req.save(update_fields=['status', 'completed_at', 'updated_at'])
            AppAPIToken.objects.filter(collector=collector, is_active=True).exclude(id=api_token.id).update(is_active=False)
            return api_response(True, '登录成功（换绑完成）', {
                'token': api_token.token,
                'expires_at': timezone.localtime(api_token.expires_at).strftime('%Y-%m-%d %H:%M:%S'),
                'collector': {
                    'id': collector.id,
                    'username': collector.username,
                    'display_name': collector.display_name,
                },
            })

    if collector.bound_device_id and collector.bound_device_id != device_id:
        return api_response(False, '设备未授权，请发起设备换绑申请', status=403, data={
            'error_code': 'DEVICE_MISMATCH',
        })

    collector.bind_device(device_id, device_info)
    collector.reset_login_failures()
    collector.last_login_at = timezone.now()
    collector.last_login_ip = get_client_ip(request)
    collector.save(update_fields=['last_login_at', 'last_login_ip', 'updated_at'])
    api_token = issue_token(collector, device_id)
    return api_response(True, '登录成功', {
        'token': api_token.token,
        'expires_at': timezone.localtime(api_token.expires_at).strftime('%Y-%m-%d %H:%M:%S'),
        'collector': {
            'id': collector.id,
            'username': collector.username,
            'display_name': collector.display_name,
        },
    })


@csrf_exempt
@require_http_methods(['POST'])
def mobile_logout(request):
    collector, api_token, err = _require_collector(request)
    if err:
        return err
    AppAPIToken.objects.filter(collector=collector, is_active=True).update(is_active=False)
    return api_response(True, '已退出登录')


@csrf_exempt
@require_http_methods(['GET'])
def mobile_projects(request):
    collector, _, err = _require_collector(request)
    if err:
        return err

    permissions = AppProjectPermission.objects.filter(collector=collector, is_active=True).order_by('platform', 'item_name')
    platform_map = {}
    total = 0
    for perm in permissions:
        platform_map.setdefault(perm.platform or '未知', []).append({
            'poiId': perm.poi_id,
            'itemName': perm.item_name,
        })
        total += 1
    platforms = [{'platform': name, 'items': items} for name, items in platform_map.items()]
    return api_response(True, '获取成功', {'platforms': platforms, 'total_count': total})


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def mobile_comments(request):
    if request.method == 'GET':
        return _mobile_comments_list(request)
    return _mobile_comments_create(request)


def _mobile_comments_list(request):
    collector, _, err = _require_collector(request)
    if err:
        return err

    poi_id = request.GET.get('poiId', '').strip()
    if not poi_id:
        return api_response(False, 'poiId 为必填参数', status=400)
    if not collector_has_poi(collector, poi_id):
        return api_response(False, '无权访问该项目', status=403)

    start, end = today_range()
    qs = QusetAnswer.objects.filter(poiId=str(poi_id), release_time__gte=start, release_time__lt=end)
    if request.GET.get('mine') in ('1', 'true', 'True'):
        mine_ids = AppCommentSubmission.objects.filter(collector=collector).values_list('comment_id', flat=True)
        qs = qs.filter(comment_id__in=mine_ids)

    page = max(int(request.GET.get('page', 1) or 1), 1)
    page_size = min(max(int(request.GET.get('page_size', 20) or 20), 1), 100)
    total = qs.count()
    offset = (page - 1) * page_size
    items = [serialize_comment(r) for r in qs.order_by('-release_time')[offset:offset + page_size]]
    return api_response(True, '获取成功', {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
    })


def _mobile_comments_create(request):
    collector, _, err = _require_collector(request)
    if err:
        return err
    try:
        data = parse_json(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    poi_id = str(data.get('poiId', '')).strip()
    if not poi_id:
        return api_response(False, 'poiId 不能为空', status=400)
    if not collector_has_poi(collector, poi_id):
        return api_response(False, '无权向该项目写入数据', status=403)

    try:
        payload = build_comment_payload(data, poi_id)
    except ValueError as exc:
        return api_response(False, str(exc), status=400)

    record, error = save_comment_for_collector(collector, payload)
    if error:
        return api_response(False, error, status=403)
    return api_response(True, '保存成功', {'comment': serialize_comment(record)})


@csrf_exempt
@require_http_methods(['PUT'])
def mobile_comment_detail(request, comment_id):
    collector, _, err = _require_collector(request)
    if err:
        return err
    try:
        data = parse_json(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    try:
        record = QusetAnswer.objects.get(comment_id=comment_id)
    except QusetAnswer.DoesNotExist:
        return api_response(False, '评论不存在', status=404)

    if not collector_has_poi(collector, record.poiId):
        return api_response(False, '无权修改该项目评论', status=403)

    submission = AppCommentSubmission.objects.filter(comment_id=comment_id).first()
    if not submission or submission.collector_id != collector.id:
        return api_response(False, '只能修改自己上报的评论', status=403)

    start, end = today_range()
    if not (record.release_time >= start and record.release_time < end):
        return api_response(False, '只能修改当天的评论', status=403)

    if 'user_name' in data and str(data.get('user_name', '')).strip() != (record.user_name or ''):
        return api_response(False, '不允许修改 user_name（会导致 comment_id 变化）', status=400)

    if 'comment_content' in data:
        record.comment_content = str(data.get('comment_content') or '')
    if 'comment_grade' in data:
        record.comment_grade = str(data.get('comment_grade') or '')
    if 'comment_num' in data:
        record.comment_num = float(data.get('comment_num') or 0)
    if 'like_num' in data:
        record.like_num = int(data.get('like_num') or 0)
    if 'reply_num' in data:
        record.reply_num = int(data.get('reply_num') or 0)
    if 'c_num' in data:
        record.c_num = int(data.get('c_num') or 0)
    if 'user_id' in data:
        record.user_id = str(data.get('user_id') or '0')
    if 'reply_content' in data:
        record.reply_content = str(data.get('reply_content') or '')
    if 'reply_video' in data:
        record.reply_video = int(data.get('reply_video') or 0)
    if 'reply_img' in data:
        record.reply_img = int(data.get('reply_img') or 0)
    if 'release_time' in data and data.get('release_time'):
        try:
            record.release_time = build_comment_payload({
                'user_name': record.user_name,
                'comment_content': record.comment_content,
                'comment_grade': record.comment_grade,
                'release_time': data.get('release_time'),
            }, record.poiId)['release_time']
        except ValueError as exc:
            return api_response(False, str(exc), status=400)

    record.save()
    AppCommentSubmission.objects.filter(comment_id=comment_id).update(updated_at=timezone.now())
    return api_response(True, '更新成功', {'comment': serialize_comment(record)})


@csrf_exempt
@require_http_methods(['POST'])
def mobile_rebind_request(request):
    try:
        data = parse_json(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    username = str(data.get('username', '')).strip()
    password = data.get('password', '')
    device_id = get_device_id(request, data)
    device_info = str(data.get('device_info', '') or '')
    captcha_id = data.get('captcha_id', '')
    captcha_code = data.get('captcha_code', '')

    if not all([username, password, device_id, captcha_id, captcha_code]):
        return api_response(False, 'username、password、device_id、captcha_id、captcha_code 均为必填', status=400)
    if not verify_captcha(captcha_id, captcha_code):
        return api_response(False, '验证码错误或已过期', status=400)

    try:
        collector = AppCollector.objects.get(username=username)
    except AppCollector.DoesNotExist:
        return api_response(False, '用户名或密码错误', status=401)
    if not collector.check_password(password):
        return api_response(False, '用户名或密码错误', status=401)
    if not collector.is_active:
        return api_response(False, '账号已禁用', status=403)
    if not collector.bound_device_id:
        return api_response(False, '当前账号尚未绑定设备，请直接登录完成首次绑定', status=400)
    if collector.bound_device_id == device_id:
        return api_response(False, '当前设备已绑定，无需换绑', status=400)

    existing = active_rebind_request(collector)
    if existing:
        expire_rebind_if_needed(existing)
        if existing.status not in AppDeviceRebindRequest.TERMINAL_STATUSES:
            return api_response(False, '已有进行中的换绑申请', status=400, data={
                'request_id': existing.id,
                'request_no': existing.request_no,
                'status': existing.status,
            })

    verify_code = generate_verify_code()
    minutes = getattr(settings, 'MOBILE_REBIND_VERIFY_MINUTES', 15)
    req = AppDeviceRebindRequest.objects.create(
        request_no=generate_request_no(),
        collector=collector,
        old_device_id=collector.bound_device_id,
        new_device_id=device_id,
        new_device_info=device_info,
        verify_code_hash=hash_verify_code(verify_code),
        verify_code_expires_at=timezone.now() + timedelta(minutes=minutes),
        request_ip=get_client_ip(request),
    )
    cache_key = f'rebind_plain_code:{req.id}'
    from django.core.cache import cache
    cache.set(cache_key, verify_code, timeout=minutes * 60)
    return api_response(True, '换绑申请已创建，请在旧设备查看验证码', {
        'request_id': req.id,
        'request_no': req.request_no,
        'status': req.status,
        'verify_expires_at': timezone.localtime(req.verify_code_expires_at).strftime('%Y-%m-%d %H:%M:%S'),
    })


@csrf_exempt
@require_http_methods(['GET'])
def mobile_rebind_pending(request):
    collector, _, err = _require_collector(request)
    if err:
        return err

    req = AppDeviceRebindRequest.objects.filter(
        collector=collector,
        status=AppDeviceRebindRequest.STATUS_PENDING_OLD,
    ).order_by('-created_at').first()
    if not req:
        return api_response(True, '暂无待验证换绑申请', {'pending': False})
    expire_rebind_if_needed(req)
    if req.status != AppDeviceRebindRequest.STATUS_PENDING_OLD:
        return api_response(True, '暂无待验证换绑申请', {'pending': False})

    from django.core.cache import cache
    verify_code = cache.get(f'rebind_plain_code:{req.id}')
    if not verify_code:
        return api_response(False, '验证码已过期，请重新发起换绑', status=400)

    return api_response(True, 'ok', {
        'pending': True,
        'request_id': req.id,
        'request_no': req.request_no,
        'new_device_info': req.new_device_info,
        'verify_code': verify_code,
        'verify_expires_at': timezone.localtime(req.verify_code_expires_at).strftime('%Y-%m-%d %H:%M:%S'),
        'status': req.status,
    })


@csrf_exempt
@require_http_methods(['POST'])
def mobile_rebind_verify(request):
    try:
        data = parse_json(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    request_id = data.get('request_id')
    verify_code = str(data.get('verify_code', '')).strip()
    if not request_id or not verify_code:
        return api_response(False, 'request_id 与 verify_code 为必填', status=400)

    try:
        req = AppDeviceRebindRequest.objects.select_related('collector').get(id=request_id)
    except AppDeviceRebindRequest.DoesNotExist:
        return api_response(False, '换绑申请不存在', status=404)

    expire_rebind_if_needed(req)
    if req.status != AppDeviceRebindRequest.STATUS_PENDING_OLD:
        return api_response(False, '换绑申请状态无效或已过期', status=400)
    if req.verify_code_expires_at < timezone.now():
        req.status = AppDeviceRebindRequest.STATUS_EXPIRED
        req.save(update_fields=['status', 'updated_at'])
        return api_response(False, '验证码已过期', status=400)

    max_attempts = getattr(settings, 'MOBILE_REBIND_MAX_VERIFY_ATTEMPTS', 5)
    if req.verify_attempts >= max_attempts:
        req.status = AppDeviceRebindRequest.STATUS_CANCELLED
        req.save(update_fields=['status', 'updated_at'])
        return api_response(False, '验证失败次数过多，申请已作废', status=400)

    if hash_verify_code(verify_code) != req.verify_code_hash:
        req.verify_attempts += 1
        req.save(update_fields=['verify_attempts', 'updated_at'])
        return api_response(False, '验证码错误', status=400)

    req.status = AppDeviceRebindRequest.STATUS_PENDING_ADMIN
    req.old_verified_at = timezone.now()
    req.save(update_fields=['status', 'old_verified_at', 'updated_at'])
    from django.core.cache import cache
    cache.delete(f'rebind_plain_code:{req.id}')
    return api_response(True, '验证成功，已提交管理员审批', {
        'request_id': req.id,
        'request_no': req.request_no,
        'status': req.status,
    })


@csrf_exempt
@require_http_methods(['GET'])
def mobile_rebind_status(request):
    request_id = request.GET.get('request_id', '').strip()
    request_no = request.GET.get('request_no', '').strip()
    if not request_id and not request_no:
        return api_response(False, 'request_id 或 request_no 必填其一', status=400)

    qs = AppDeviceRebindRequest.objects.all()
    if request_id:
        qs = qs.filter(id=request_id)
    else:
        qs = qs.filter(request_no=request_no)
    req = qs.first()
    if not req:
        return api_response(False, '换绑申请不存在', status=404)
    expire_rebind_if_needed(req)
    return api_response(True, 'ok', {
        'request_id': req.id,
        'request_no': req.request_no,
        'status': req.status,
        'reject_reason': req.reject_reason or '',
        'approved_expires_at': timezone.localtime(req.approved_expires_at).strftime('%Y-%m-%d %H:%M:%S') if req.approved_expires_at else '',
    })


@csrf_exempt
@require_http_methods(['POST'])
def mobile_rebind_complete(request):
    try:
        data = parse_json(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    request_id = data.get('request_id')
    username = str(data.get('username', '')).strip()
    password = data.get('password', '')
    device_id = get_device_id(request, data)
    device_info = str(data.get('device_info', '') or '')
    captcha_id = data.get('captcha_id', '')
    captcha_code = data.get('captcha_code', '')

    if not all([request_id, username, password, device_id, captcha_id, captcha_code]):
        return api_response(False, 'request_id、username、password、device_id、captcha_id、captcha_code 均为必填', status=400)
    if not verify_captcha(captcha_id, captcha_code):
        return api_response(False, '验证码错误或已过期', status=400)

    try:
        req = AppDeviceRebindRequest.objects.select_related('collector').get(id=request_id)
    except AppDeviceRebindRequest.DoesNotExist:
        return api_response(False, '换绑申请不存在', status=404)

    expire_rebind_if_needed(req)
    if req.status != AppDeviceRebindRequest.STATUS_APPROVED:
        return api_response(False, '换绑申请尚未批准或已失效', status=400)
    if req.new_device_id != device_id:
        return api_response(False, 'device_id 与申请不一致', status=400)

    collector = req.collector
    if collector.username != username or not collector.check_password(password):
        return api_response(False, '用户名或密码错误', status=401)

    collector.bind_device(device_id, device_info)
    collector.reset_login_failures()
    collector.last_login_at = timezone.now()
    collector.last_login_ip = get_client_ip(request)
    collector.save(update_fields=['last_login_at', 'last_login_ip', 'updated_at'])
    api_token = issue_token(collector, device_id)
    req.status = AppDeviceRebindRequest.STATUS_COMPLETED
    req.completed_at = timezone.now()
    req.save(update_fields=['status', 'completed_at', 'updated_at'])
    return api_response(True, '换绑完成', {
        'token': api_token.token,
        'expires_at': timezone.localtime(api_token.expires_at).strftime('%Y-%m-%d %H:%M:%S'),
        'collector': {
            'id': collector.id,
            'username': collector.username,
            'display_name': collector.display_name,
        },
    })


@csrf_exempt
@require_http_methods(['POST'])
def mobile_rebind_cancel(request):
    try:
        data = parse_json(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    request_id = data.get('request_id')
    if not request_id:
        return api_response(False, 'request_id 为必填', status=400)

    try:
        req = AppDeviceRebindRequest.objects.get(id=request_id)
    except AppDeviceRebindRequest.DoesNotExist:
        return api_response(False, '换绑申请不存在', status=404)

    if req.status != AppDeviceRebindRequest.STATUS_PENDING_OLD:
        return api_response(False, '当前状态不可取消', status=400)
    req.status = AppDeviceRebindRequest.STATUS_CANCELLED
    req.save(update_fields=['status', 'updated_at'])
    from django.core.cache import cache
    cache.delete(f'rebind_plain_code:{req.id}')
    return api_response(True, '已取消换绑申请')
