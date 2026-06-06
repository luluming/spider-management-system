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
    authenticate_collector_login,
    build_comment_payload,
    cancel_rebind_request,
    collector_projects_response,
    create_device_change_request,
    expire_rebind_if_needed,
    extract_login_password,
    finish_collector_login,
    generate_captcha_image,
    generate_request_no,
    generate_verify_code,
    get_client_ip,
    get_device_id,
    hash_verify_code,
    issue_token,
    collector_has_poi,
    parse_json,
    parse_request_data,
    pending_device_change_response,
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


def _create_device_change_request(collector, device_id, device_info, request, *, is_register=False):
    """创建设备注册/换绑申请，调试阶段可跳过旧设备验证直接进入待管理员审批。"""
    is_first_device = not collector.bound_device_id
    if not is_register and not is_first_device and collector.bound_device_id == device_id:
        return None, api_response(False, '当前设备已绑定，无需换绑', status=400)

    req, created = create_device_change_request(
        collector, device_id, device_info, request, is_register=is_register,
    )
    if not req:
        return None, api_response(False, '当前设备已绑定，无需换绑', status=400)

    if not created:
        message = (
            '设备注册申请待管理员审批' if is_first_device
            else '换绑申请已提交，请等待管理员审批'
        )
        return req, api_response(True, message, {
            'request_id': req.id,
            'request_no': req.request_no,
            'status': req.status,
            'new_device_id': req.new_device_id,
            'new_device_info': req.new_device_info,
            'is_first_device': is_first_device,
            'verify_expires_at': timezone.localtime(req.verify_code_expires_at).strftime('%Y-%m-%d %H:%M:%S'),
        })

    if req.status == AppDeviceRebindRequest.STATUS_PENDING_OLD:
        message = '换绑申请已创建，请在旧设备查看验证码'
    elif is_first_device:
        message = '设备注册申请已提交，请等待管理员审批'
    else:
        message = '换绑申请已提交，请等待管理员审批'

    return req, api_response(True, message, {
        'request_id': req.id,
        'request_no': req.request_no,
        'status': req.status,
        'new_device_id': req.new_device_id,
        'new_device_info': req.new_device_info,
        'is_first_device': is_first_device,
        'verify_expires_at': timezone.localtime(req.verify_code_expires_at).strftime('%Y-%m-%d %H:%M:%S'),
    })


def _parse_device_change_payload(request):
    try:
        data = parse_request_data(request)
    except json.JSONDecodeError:
        return None, api_response(False, 'JSON 格式错误', status=400)

    username = str(
        data.get('username') or data.get('user_name') or data.get('userName') or '',
    ).strip()
    password = extract_login_password(data)
    device_id = get_device_id(request, data)
    device_info = str(data.get('device_info', '') or '')
    captcha_id = data.get('captcha_id', '')
    captcha_code = data.get('captcha_code', '')
    captcha_required = getattr(settings, 'MOBILE_LOGIN_CAPTCHA_REQUIRED', True)

    if not username or not password or not device_id:
        return None, api_response(
            False,
            'username、password、device_id 均为必填',
            status=400,
            data={'error_code': 'MISSING_FIELDS'},
        )
    if captcha_required:
        if not captcha_id or not captcha_code:
            return None, api_response(
                False,
                'captcha_id、captcha_code 为必填',
                status=400,
                data={'error_code': 'CAPTCHA_REQUIRED'},
            )
        if not verify_captcha(captcha_id, captcha_code):
            return None, api_response(False, '验证码错误或已过期', status=400)

    try:
        collector = AppCollector.objects.get(username=username)
    except AppCollector.DoesNotExist:
        return None, api_response(False, '用户名或密码错误', status=401)
    if not collector.check_password(password):
        return None, api_response(False, '用户名或密码错误', status=401)
    if not collector.is_active:
        return None, api_response(False, '账号已禁用', status=403)

    return (collector, device_id, device_info, data), None


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
        data = parse_request_data(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    device_id = get_device_id(request, data)
    device_info = str(data.get('device_info', '') or '')
    captcha_id = data.get('captcha_id', '')
    captcha_code = data.get('captcha_code', '')
    captcha_required = getattr(settings, 'MOBILE_LOGIN_CAPTCHA_REQUIRED', True)
    password = extract_login_password(data)
    username = str(data.get('username') or data.get('user_name') or data.get('userName') or '').strip()

    if not username or not password or not device_id:
        return api_response(False, 'username、password、device_id 均为必填', status=400, data={
            'error_code': 'MISSING_FIELDS',
            'hint': '请确认 Content-Type 为 application/json 或 form，且 password 字段名正确',
        })
    if captcha_required:
        if not captcha_id or not captcha_code:
            return api_response(False, 'captcha_id、captcha_code 为必填', status=400)
        if not verify_captcha(captcha_id, captcha_code):
            return api_response(False, '验证码错误或已过期', status=400)

    collector, err = authenticate_collector_login(data, request)
    if err:
        return err
    if not collector:
        return api_response(False, '用户名或密码错误', status=401, data={
            'error_code': 'AUTH_FAILED',
            'hint': '请使用「采集用户管理」中创建的 App 采集员账号，不是 Web 后台登录账号',
        })

    return finish_collector_login(request, collector, device_id, device_info)


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

    return collector_projects_response(collector)


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
        data = parse_request_data(request)
    except json.JSONDecodeError:
        return api_response(False, 'JSON 格式错误', status=400)

    poi_id = str(data.get('poiId') or data.get('poi_id') or '').strip()
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
@require_http_methods(['POST'])
def mobile_quset_answer_insert(request):
    """向 quset_answer 表插入/更新评论（与 POST /comments/ 相同）。"""
    return _mobile_comments_create(request)


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
def mobile_device_register_request(request):
    """新设备注册申请（账号尚未绑定设备，或需管理员审批绑定）。"""
    payload, err = _parse_device_change_payload(request)
    if err:
        return err
    collector, device_id, device_info, _ = payload
    if collector.bound_device_id and collector.bound_device_id != device_id:
        return api_response(False, '账号已绑定其他设备，请使用换绑接口', status=400, data={
            'error_code': 'DEVICE_ALREADY_BOUND',
        })
    _, resp = _create_device_change_request(
        collector, device_id, device_info, request, is_register=True,
    )
    return resp


@csrf_exempt
@require_http_methods(['POST'])
def mobile_rebind_request(request):
    payload, err = _parse_device_change_payload(request)
    if err:
        return err
    collector, device_id, device_info, _ = payload
    if not collector.bound_device_id:
        _, resp = _create_device_change_request(
            collector, device_id, device_info, request, is_register=True,
        )
        return resp
    _, resp = _create_device_change_request(
        collector, device_id, device_info, request, is_register=False,
    )
    return resp


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
