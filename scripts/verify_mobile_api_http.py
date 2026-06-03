#!/usr/bin/env python
"""HTTP-level verification of Mobile API (uses shared file cache for captcha)."""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:8000/api/v1/mobile'


def http(method, path, body=None, headers=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
    import django
    django.setup()
    from django.core.cache import cache
    from django.utils import timezone
    from spiders.models import AppCollector, AppProjectPermission

    username, password, device_id, poi_id = 'api_test_user', 'ApiTest@2026', 'dev-test-001', '678'
    c = AppCollector.objects.get(username=username)
    c.set_password(password)
    c.bound_device_id = device_id
    c.is_active = True
    c.failed_login_count = 0
    c.locked_until = None
    c.save()
    AppProjectPermission.objects.get_or_create(
        collector=c, poi_id=poi_id,
        defaults={'item_name': '测试', 'platform': '去哪儿', 'is_active': True},
    )

    passed = 0
    st, body = http('GET', '/captcha/')
    assert st == 200 and body['success']
    cid = body['data']['captcha_id']
    code = cache.get(f'mobile_captcha:{cid}')
    assert code, 'captcha missing from shared cache'
    passed += 1
    print('[PASS] HTTP GET /captcha/ + cache read')

    st, body = http('POST', '/login/', {
        'username': username, 'password': password, 'device_id': device_id,
        'captcha_id': cid, 'captcha_code': code,
    })
    assert st == 200 and body['success'], body
    token = body['data']['token']
    passed += 1
    print('[PASS] HTTP POST /login/')

    auth = {'Authorization': f'Bearer {token}', 'X-Device-Id': device_id}
    st, body = http('GET', '/projects/', headers=auth)
    assert st == 200 and body['success']
    passed += 1
    print('[PASS] HTTP GET /projects/')

    now = timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')
    st, body = http('POST', '/comments/', {
        'poiId': poi_id, 'user_name': 'HTTP测试', 'comment_content': 'http-verify',
        'comment_grade': '5', 'release_time': now,
    }, auth)
    assert st == 200 and body['success'], body
    passed += 1
    print('[PASS] HTTP POST /comments/')

    st, body = http('POST', '/logout/', {}, auth)
    assert st == 200 and body['success']
    passed += 1
    print('[PASS] HTTP POST /logout/')

    print(f'\nHTTP verification: {passed}/5 passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
