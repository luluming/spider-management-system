import hashlib
import json
import random
import re
import secrets
import string
import uuid
from datetime import datetime, timedelta
from io import BytesIO

import base64
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from spiders.models import (
    AppAPIToken,
    AppCollector,
    AppCommentSubmission,
    AppDeviceRebindRequest,
    AppProjectPermission,
    QusetAnswer,
)


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def api_response(success, message='', data=None, status=200):
    payload = {'success': success, 'message': message}
    if data is not None:
        payload['data'] = data
    return JsonResponse(payload, status=status)


def parse_json(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode('utf-8'))


def parse_request_data(request):
    """解析 JSON 或 form 表单请求体（兼容 App 不同 Content-Type）。"""
    content_type = (request.content_type or '').lower()
    if request.POST:
        return {key: request.POST.get(key) for key in request.POST}
    if 'application/json' in content_type or request.body:
        try:
            return parse_json(request)
        except json.JSONDecodeError:
            if 'application/x-www-form-urlencoded' in content_type and request.body:
                from urllib.parse import parse_qs
                parsed = parse_qs(request.body.decode('utf-8'), keep_blank_values=True)
                return {k: (v[0] if v else '') for k, v in parsed.items()}
            if 'application/json' in content_type:
                raise
    return {}


def get_bearer_token(request):
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return ''


def normalize_device_id(raw):
    """提取标准 UUID 设备 ID，避免误粘贴「UUID + 设备描述」被当成 ID。"""
    val = str(raw or '').strip()
    if not val:
        return ''
    match = re.match(
        r'^([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})',
        val,
    )
    if match:
        return match.group(1).lower()
    if ' ' in val:
        return val.split()[0]
    return val


def get_device_id(request, data=None):
    if data and data.get('device_id'):
        return normalize_device_id(data.get('device_id'))
    header_val = request.META.get('HTTP_X_DEVICE_ID', '')
    return normalize_device_id(header_val)


def generate_captcha_image():
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    width, height = 180, 60
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)
    for _ in range(5):
        start = (random.randint(0, width), random.randint(0, height))
        end = (random.randint(0, width), random.randint(0, height))
        draw.line([start, end], fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)), width=2)
    try:
        font = ImageFont.truetype('/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf', 36)
    except OSError:
        try:
            font = ImageFont.truetype('/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf', 36)
        except OSError:
            font = ImageFont.load_default()
    for i, char in enumerate(captcha_text):
        draw.text((10 + i * 30, 5), char, font=font, fill=(random.randint(0, 100), random.randint(0, 100), random.randint(0, 100)))
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    return captcha_text, img_str


def store_captcha(captcha_text):
    captcha_id = uuid.uuid4().hex
    cache.set(f'mobile_captcha:{captcha_id}', captcha_text.upper(), timeout=300)
    return captcha_id


def verify_captcha(captcha_id, captcha_code, consume=True):
    if not captcha_id or not captcha_code:
        return False
    key = f'mobile_captcha:{captcha_id}'
    expected = cache.get(key)
    if not expected:
        return False
    ok = expected == str(captcha_code).upper().strip()
    if ok and consume:
        cache.delete(key)
    return ok


def extract_login_password(data):
    for key in ('password', 'pwd', 'pass', 'userPassword', 'user_password', 'Password'):
        val = data.get(key)
        if val is not None and str(val).strip() != '':
            return str(val)
    return ''


def finish_collector_login(request, collector, device_id, device_info=''):
    """密码已验证通过后，完成设备校验并签发 Token。"""
    from spiders.models import AppAPIToken, AppDeviceRebindRequest

    device_id = str(device_id or '').strip()
    device_info = str(device_info or '').strip()
    if not device_id:
        return api_response(False, 'device_id 为必填', status=400)

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
        req, _ = create_device_change_request(
            collector, device_id, device_info, request, is_register=False,
        )
        if req and req.status in AppDeviceRebindRequest.ADMIN_PENDING_STATUSES:
            return pending_device_change_response(req, is_first_device=False)
        if req and req.status == AppDeviceRebindRequest.STATUS_PENDING_OLD:
            return api_response(False, '设备未授权，换绑申请已创建，请在旧设备查看验证码', status=403, data={
                'error_code': 'PENDING_OLD_VERIFY',
                'request_id': req.id,
                'request_no': req.request_no,
                'status': req.status,
            })
        return api_response(False, '设备未授权，请发起设备换绑申请', status=403, data={
            'error_code': 'DEVICE_MISMATCH',
            'bound_device_id': collector.bound_device_id,
        })

    if not collector.bound_device_id and getattr(settings, 'MOBILE_DEVICE_REGISTER_REQUIRES_ADMIN', False):
        pending = AppDeviceRebindRequest.objects.filter(
            collector=collector,
            status__in=AppDeviceRebindRequest.ADMIN_PENDING_STATUSES,
        ).order_by('-created_at').first()
        if pending:
            return pending_device_change_response(pending, is_first_device=True)
        req, _ = create_device_change_request(
            collector, device_id, device_info, request, is_register=True,
        )
        if req:
            return pending_device_change_response(req, is_first_device=True)
        return api_response(False, '请先提交设备注册申请，或由管理员在后台绑定设备', status=403, data={
            'error_code': 'DEVICE_REGISTER_REQUIRED',
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


def authenticate_collector_login(data, request):
    """校验采集员账号密码，返回 (collector, error_response)。"""
    from spiders.models import AppCollector

    username = str(data.get('username') or data.get('user_name') or data.get('userName') or '').strip()
    password = extract_login_password(data)
    if not username or not password:
        return None, api_response(False, 'username 与 password 为必填', status=400)

    try:
        collector = AppCollector.objects.get(username=username)
    except AppCollector.DoesNotExist:
        return None, None

    if not collector.is_active:
        return None, api_response(False, '账号已禁用', status=403, data={'error_code': 'ACCOUNT_DISABLED'})
    if collector.is_locked():
        locked_until = timezone.localtime(collector.locked_until).strftime('%Y-%m-%d %H:%M:%S')
        return None, api_response(False, f'账号已锁定，请 {locked_until} 后再试', status=423, data={'error_code': 'ACCOUNT_LOCKED'})

    if not collector.check_password(password):
        collector.record_failed_login()
        import logging
        logging.getLogger('spiders.mobile').warning(
            'App login password mismatch: username=%s ip=%s',
            username, get_client_ip(request),
        )
        return None, api_response(False, '用户名或密码错误', status=401, data={
            'error_code': 'AUTH_FAILED',
            'hint': '账号已存在但密码不正确，请在 Web「采集用户管理」中重置密码后再试',
        })

    return collector, None


def authenticate_collector(request):
    token = get_bearer_token(request)
    if not token:
        return None, None
    try:
        api_token = AppAPIToken.objects.select_related('collector').get(token=token, is_active=True)
    except AppAPIToken.DoesNotExist:
        return None, None
    if api_token.is_expired():
        api_token.is_active = False
        api_token.save(update_fields=['is_active'])
        return None, None
    api_token.last_used = timezone.now()
    api_token.save(update_fields=['last_used'])
    return api_token.collector, api_token


def issue_token(collector, device_id):
    token = secrets.token_urlsafe(32)
    days = getattr(settings, 'MOBILE_API_TOKEN_DAYS', 30)
    expires_at = timezone.now() + timedelta(days=days)
    AppAPIToken.objects.filter(collector=collector, is_active=True).update(is_active=False)
    api_token = AppAPIToken.objects.create(
        collector=collector,
        token=token,
        device_id=device_id or '',
        expires_at=expires_at,
        is_active=True,
    )
    return api_token


def collector_has_poi(collector, poi_id):
    return AppProjectPermission.objects.filter(
        collector=collector,
        poi_id=str(poi_id),
        is_active=True,
    ).exists()


def collector_projects_response(collector, success_msg='获取成功', empty_msg='暂无授权项目', include_data_array=True):
    """返回采集员授权项目。App Gson 将 data 解析为 List<Project>，故 data 为项目数组。"""
    payload = build_collector_projects_payload(collector)
    message = success_msg if payload['total_count'] else empty_msg
    body = {
        'success': True,
        'message': message,
        'projects': payload['projects'],
        'platforms': payload['platforms'],
        'total_count': payload['total_count'],
    }
    if include_data_array:
        body['data'] = payload['projects']
    return JsonResponse(body)


def build_collector_projects_payload(collector):
    """构建采集员授权项目列表（兼容 v1 分组结构与旧版 flat projects 列表）。"""
    permissions = AppProjectPermission.objects.filter(
        collector=collector, is_active=True,
    ).order_by('platform', 'item_name')
    platform_map = {}
    projects = []
    for perm in permissions:
        poi_id = str(perm.poi_id)
        item = {
            'poiId': poi_id,
            'poi_id': poi_id,
            'itemName': perm.item_name,
            'name': perm.item_name,
            'platform': perm.platform or '',
        }
        projects.append(item)
        platform_map.setdefault(perm.platform or '未知', []).append({
            'poiId': poi_id,
            'itemName': perm.item_name,
        })
    platforms = [{'platform': name, 'items': items} for name, items in platform_map.items()]
    return {
        'platforms': platforms,
        'projects': projects,
        'total_count': len(projects),
    }


def get_collector_by_app_token(token):
    if not token:
        return None
    try:
        api_token = AppAPIToken.objects.select_related('collector').get(token=token, is_active=True)
    except AppAPIToken.DoesNotExist:
        return None
    if api_token.is_expired():
        api_token.is_active = False
        api_token.save(update_fields=['is_active'])
        return None
    api_token.last_used = timezone.now()
    api_token.save(update_fields=['last_used'])
    return api_token.collector


def make_comment_id(user_name, comment_grade, comment_content):
    raw = f'{user_name}{comment_grade}{comment_content}'
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def hash_verify_code(code):
    return hashlib.sha256(code.encode('utf-8')).hexdigest()


def generate_verify_code():
    return ''.join(random.choices(string.digits, k=6))


def generate_request_no():
    now = timezone.now()
    suffix = random.randint(1000, 9999)
    return f'RB{now.strftime("%Y%m%d%H%M%S")}{suffix}'


def cancel_rebind_request(req):
    req.status = AppDeviceRebindRequest.STATUS_CANCELLED
    req.save(update_fields=['status', 'updated_at'])
    cache.delete(f'rebind_plain_code:{req.id}')


def create_device_change_request(collector, device_id, device_info, request, *, is_register=False):
    """创建或复用设备注册/换绑申请，返回 (request_obj, created_new_bool)。"""
    skip_old_verify = getattr(settings, 'MOBILE_REBIND_SKIP_OLD_VERIFY', False)
    is_first_device = not collector.bound_device_id
    device_id = str(device_id or '').strip()
    device_info = str(device_info or '').strip()

    if not is_register and not is_first_device and collector.bound_device_id == device_id:
        return None, False

    existing = active_rebind_request(collector)
    if existing:
        expire_rebind_if_needed(existing)
        existing.refresh_from_db()
        if existing.status not in AppDeviceRebindRequest.TERMINAL_STATUSES:
            if (
                existing.new_device_id == device_id
                and existing.status in AppDeviceRebindRequest.ADMIN_PENDING_STATUSES
            ):
                return existing, False
            cancel_rebind_request(existing)

    minutes = getattr(settings, 'MOBILE_REBIND_VERIFY_MINUTES', 15)
    if skip_old_verify or is_first_device:
        status = AppDeviceRebindRequest.STATUS_PENDING_ADMIN
        verify_hash = ''
        verify_expires = timezone.now() + timedelta(minutes=minutes)
        verify_code = None
    else:
        status = AppDeviceRebindRequest.STATUS_PENDING_OLD
        verify_code = generate_verify_code()
        verify_hash = hash_verify_code(verify_code)
        verify_expires = timezone.now() + timedelta(minutes=minutes)

    req = AppDeviceRebindRequest.objects.create(
        request_no=generate_request_no(),
        collector=collector,
        old_device_id=collector.bound_device_id or '',
        new_device_id=device_id,
        new_device_info=device_info,
        verify_code_hash=verify_hash,
        verify_code_expires_at=verify_expires,
        status=status,
        request_ip=get_client_ip(request),
    )
    if status == AppDeviceRebindRequest.STATUS_PENDING_OLD and verify_code:
        cache.set(f'rebind_plain_code:{req.id}', verify_code, timeout=minutes * 60)
    return req, True


def pending_device_change_response(req, *, is_first_device=False):
    message = '设备注册申请待管理员审批' if is_first_device else '换绑申请已提交，请等待管理员审批'
    return api_response(False, message, status=403, data={
        'error_code': 'PENDING_ADMIN',
        'request_id': req.id,
        'request_no': req.request_no,
        'status': req.status,
        'new_device_id': req.new_device_id,
        'new_device_info': req.new_device_info,
        'is_first_device': is_first_device,
        'verify_expires_at': timezone.localtime(req.verify_code_expires_at).strftime('%Y-%m-%d %H:%M:%S'),
    })


def active_rebind_request(collector):
    return AppDeviceRebindRequest.objects.filter(
        collector=collector,
    ).exclude(status__in=AppDeviceRebindRequest.TERMINAL_STATUSES).order_by('-created_at').first()


def expire_rebind_if_needed(req):
    now = timezone.now()
    changed = False
    if req.status == AppDeviceRebindRequest.STATUS_PENDING_OLD and req.verify_code_expires_at < now:
        req.status = AppDeviceRebindRequest.STATUS_EXPIRED
        changed = True
    elif req.status == AppDeviceRebindRequest.STATUS_PENDING_ADMIN:
        if req.created_at + timedelta(hours=getattr(settings, 'MOBILE_REBIND_ADMIN_HOURS', 24)) < now:
            req.status = AppDeviceRebindRequest.STATUS_EXPIRED
            changed = True
    elif req.status == AppDeviceRebindRequest.STATUS_APPROVED and req.approved_expires_at and req.approved_expires_at < now:
        req.status = AppDeviceRebindRequest.STATUS_EXPIRED
        changed = True
    if changed:
        req.save(update_fields=['status', 'updated_at'])
    return req


def parse_release_time(value):
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            raise ValueError('release_time 格式无效')
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def today_range():
    now = timezone.localtime()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def serialize_comment(record):
    return {
        'comment_id': record.comment_id,
        'poiId': str(record.poiId),
        'user_name': record.user_name or '',
        'comment_content': record.comment_content or '',
        'comment_grade': record.comment_grade if record.comment_grade is not None else '',
        'comment_num': record.comment_num,
        'like_num': record.like_num,
        'reply_num': record.reply_num,
        'c_num': record.c_num,
        'user_id': record.user_id or '',
        'reply_content': record.reply_content or '',
        'reply_video': record.reply_video,
        'reply_img': record.reply_img,
        'release_time': timezone.localtime(record.release_time).strftime('%Y-%m-%d %H:%M:%S') if record.release_time else '',
        'create_time': timezone.localtime(record.create_time).strftime('%Y-%m-%d %H:%M:%S') if record.create_time else '',
    }


def build_comment_payload(data, poi_id):
    user_name = str(data.get('user_name', '')).strip()
    comment_content = str(data.get('comment_content', '')).strip()
    comment_grade = str(data.get('comment_grade', '0')).strip()
    if not user_name:
        raise ValueError('user_name 不能为空')
    if not comment_content:
        raise ValueError('comment_content 不能为空')
    if not comment_grade:
        raise ValueError('comment_grade 不能为空')
    release_time = parse_release_time(data.get('release_time'))
    comment_id = make_comment_id(user_name, comment_grade, comment_content)
    user_id_raw = data.get('user_id', '')
    user_id = str(user_id_raw).strip() if user_id_raw not in (None, '') else '0'
    return {
        'comment_id': comment_id,
        'poiId': str(poi_id),
        'user_name': user_name,
        'comment_content': comment_content,
        'comment_grade': comment_grade,
        'comment_num': float(data.get('comment_num', 0) or 0),
        'like_num': int(data.get('like_num', 0) or 0),
        'reply_num': int(data.get('reply_num', 0) or 0),
        'c_num': int(data.get('c_num', 0) or 0),
        'user_id': user_id,
        'reply_content': str(data.get('reply_content', '') or ''),
        'reply_video': int(data.get('reply_video', 0) or 0),
        'reply_img': int(data.get('reply_img', 0) or 0),
        'release_time': release_time,
    }


def save_comment_for_collector(collector, payload):
    existing_sub = AppCommentSubmission.objects.filter(comment_id=payload['comment_id']).first()
    if existing_sub and existing_sub.collector_id != collector.id:
        return None, '该评论已由其他采集员上报，无法覆盖'
    now = timezone.now()
    record = QusetAnswer.objects.filter(comment_id=payload['comment_id']).first()
    if record:
        for key, value in payload.items():
            setattr(record, key, value)
        record.save()
    else:
        payload['create_time'] = now
        record = QusetAnswer.objects.create(**payload)
    AppCommentSubmission.objects.update_or_create(
        comment_id=payload['comment_id'],
        defaults={'collector': collector},
    )
    AppCommentSubmission.objects.filter(comment_id=payload['comment_id']).update(updated_at=now)
    return record, None
