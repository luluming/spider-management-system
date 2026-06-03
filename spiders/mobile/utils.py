import hashlib
import json
import random
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


def get_bearer_token(request):
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return ''


def get_device_id(request, data=None):
    if data and data.get('device_id'):
        return str(data.get('device_id')).strip()
    header_val = request.META.get('HTTP_X_DEVICE_ID', '')
    return str(header_val).strip()


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
