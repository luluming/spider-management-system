#!/usr/bin/env python
"""Live verification of App Mobile API v1 endpoints."""
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime

BASE = 'http://127.0.0.1:8000/api/v1/mobile'


def request(method, path, body=None, headers=None):
    url = BASE + path
    data = json.dumps(body).encode('utf-8') if body is not None else None
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8')
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8')
        try:
            body_json = json.loads(raw)
        except json.JSONDecodeError:
            body_json = {'raw': raw}
        return exc.code, body_json


def ok(name, status, body, expect_success=True):
    passed = status == 200 and body.get('success') is expect_success
    mark = 'PASS' if passed else 'FAIL'
    print(f'[{mark}] {name} -> HTTP {status} success={body.get("success")} msg={body.get("message", "")[:60]}')
    if not passed:
        print('       ', json.dumps(body, ensure_ascii=False)[:300])
    return passed


def main():
    from django.core.cache import cache

    import django
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
    django.setup()

    from django.utils import timezone
    from spiders.models import AppCollector, AppProjectPermission

    username = 'api_test_user'
    password = 'ApiTest@2026'
    device_id = 'dev-test-001'
    poi_id = '678'

    collector = AppCollector.objects.filter(username=username).first()
    if not collector:
        print('ERROR: api_test_user not found, create one in admin first')
        return 1
    collector.set_password(password)
    collector.is_active = True
    collector.failed_login_count = 0
    collector.locked_until = None
    collector.bound_device_id = device_id
    collector.save()

    perm = AppProjectPermission.objects.filter(collector=collector, poi_id=poi_id, is_active=True).first()
    if not perm:
        print(f'WARNING: no permission for poi {poi_id}, creating test permission')
        AppProjectPermission.objects.get_or_create(
            collector=collector,
            poi_id=poi_id,
            defaults={'item_name': '测试', 'platform': '去哪儿', 'is_active': True},
        )

    results = []

    status, body = request('GET', '/captcha/')
    results.append(ok('GET /captcha/', status, body))
    captcha_id = body.get('data', {}).get('captcha_id')
    captcha_code = cache.get(f'mobile_captcha:{captcha_id}')
    if not captcha_code:
        print('ERROR: captcha not in cache (locmem may differ between processes)')
        return 1

    status, body = request('POST', '/login/', {
        'username': username,
        'password': password,
        'device_id': device_id,
        'captcha_id': captcha_id,
        'captcha_code': captcha_code,
    })
    results.append(ok('POST /login/', status, body))
    token = body.get('data', {}).get('token')
    if not token:
        return 1

    auth = {'Authorization': f'Bearer {token}', 'X-Device-Id': device_id}

    status, body = request('GET', '/projects/', headers=auth)
    results.append(ok('GET /projects/', status, body))

    now = timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')
    comment_payload = {
        'poiId': poi_id,
        'user_name': 'API验证用户',
        'comment_content': f'API验证-{datetime.now().strftime("%H%M%S")}',
        'comment_grade': '5',
        'release_time': now,
    }
    status, body = request('POST', '/comments/', comment_payload, auth)
    results.append(ok('POST /comments/', status, body))
    comment_id = body.get('data', {}).get('comment', {}).get('comment_id')

    status, body = request('GET', f'/comments/?poiId={poi_id}&mine=1', headers=auth)
    results.append(ok('GET /comments/', status, body))

    if comment_id:
        status, body = request('PUT', f'/comments/{comment_id}/', {'like_num': 99}, auth)
        results.append(ok('PUT /comments/{id}/', status, body))

    status, body = request('GET', '/device/rebind/pending/', headers=auth)
    results.append(ok('GET /device/rebind/pending/', status, body))

    status, body = request('POST', '/logout/', {}, auth)
    results.append(ok('POST /logout/', status, body))

    status, body = request('GET', '/projects/', headers=auth)
    results.append(ok('GET /projects/ after logout (expect fail)', status, body, expect_success=False))

    passed = sum(results)
    total = len(results)
    print(f'\nResult: {passed}/{total} passed')
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
