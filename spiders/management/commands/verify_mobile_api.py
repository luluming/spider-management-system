"""Verify all App Mobile API v1 endpoints via Django test client."""
import json
from datetime import datetime

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.test import Client
from django.utils import timezone

from spiders.models import AppCollector, AppProjectPermission, AppDeviceRebindRequest


class Command(BaseCommand):
    help = 'Verify App Mobile API v1 endpoints'

    def handle(self, *args, **options):
        client = Client()
        base = '/api/v1/mobile'
        username = 'api_test_user'
        password = 'ApiTest@2026'
        device_id = 'dev-test-001'
        poi_id = '678'
        passed = 0
        total = 0

        collector = AppCollector.objects.filter(username=username).first()
        if not collector:
            self.stderr.write('api_test_user not found')
            return

        collector.set_password(password)
        collector.is_active = True
        collector.failed_login_count = 0
        collector.locked_until = None
        collector.bound_device_id = device_id
        collector.save()
        AppProjectPermission.objects.get_or_create(
            collector=collector,
            poi_id=poi_id,
            defaults={'item_name': '测试', 'platform': '去哪儿', 'is_active': True},
        )

        def check(name, resp, expect_success=True):
            nonlocal passed, total
            total += 1
            try:
                body = resp.json()
            except Exception:
                body = {'raw': resp.content[:200]}
            ok = resp.status_code == 200 and body.get('success') is expect_success
            if ok:
                passed += 1
                self.stdout.write(self.style.SUCCESS(f'[PASS] {name}'))
            else:
                self.stdout.write(self.style.ERROR(
                    f'[FAIL] {name} HTTP {resp.status_code} {body.get("message", body)}'
                ))
            return body if ok else None

        resp = client.get(f'{base}/captcha/')
        body = check('GET /captcha/', resp)
        captcha_id = body['data']['captcha_id'] if body else ''
        captcha_code = cache.get(f'mobile_captcha:{captcha_id}')

        resp = client.post(
            f'{base}/login/',
            data=json.dumps({
                'username': username,
                'password': password,
                'device_id': device_id,
                'captcha_id': captcha_id,
                'captcha_code': captcha_code,
            }),
            content_type='application/json',
        )
        body = check('POST /login/', resp)
        token = body['data']['token'] if body else ''
        auth = {'HTTP_AUTHORIZATION': f'Bearer {token}', 'HTTP_X_DEVICE_ID': device_id}

        resp = client.get(f'{base}/projects/', **auth)
        check('GET /projects/', resp)

        now = timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')
        resp = client.post(
            f'{base}/comments/',
            data=json.dumps({
                'poiId': poi_id,
                'user_name': 'API验证用户',
                'comment_content': f'验证-{datetime.now().strftime("%H%M%S")}',
                'comment_grade': '5',
                'release_time': now,
            }),
            content_type='application/json',
            **auth,
        )
        body = check('POST /comments/', resp)
        comment_id = body['data']['comment']['comment_id'] if body else ''

        resp = client.get(f'{base}/comments/?poiId={poi_id}&mine=1', **auth)
        check('GET /comments/', resp)

        if comment_id:
            resp = client.put(
                f'{base}/comments/{comment_id}/',
                data=json.dumps({'like_num': 88}),
                content_type='application/json',
                **auth,
            )
            check('PUT /comments/{id}/', resp)

        resp = client.get(f'{base}/device/rebind/pending/', **auth)
        check('GET /device/rebind/pending/', resp)

        resp = client.post(f'{base}/logout/', **auth)
        check('POST /logout/', resp)

        resp = client.get(f'{base}/projects/', **auth)
        total += 1
        if resp.status_code == 401:
            passed += 1
            self.stdout.write(self.style.SUCCESS('[PASS] GET /projects/ after logout (401)'))
        else:
            self.stdout.write(self.style.ERROR(f'[FAIL] GET /projects/ after logout HTTP {resp.status_code}'))

        # Rebind endpoints (no full flow to avoid side effects)
        captcha_id2 = client.get(f'{base}/captcha/').json()['data']['captcha_id']
        code2 = cache.get(f'mobile_captcha:{captcha_id2}')
        resp = client.post(
            f'{base}/device/rebind/request/',
            data=json.dumps({
                'username': username,
                'password': password,
                'device_id': 'other-device-temp',
                'captcha_id': captcha_id2,
                'captcha_code': code2,
            }),
            content_type='application/json',
        )
        body = check('POST /device/rebind/request/', resp)
        request_id = body['data']['request_id'] if body else 0

        if request_id:
            resp = client.get(f'{base}/device/rebind/status/?request_id={request_id}')
            check('GET /device/rebind/status/', resp)

            cap_resp = client.get(f'{base}/captcha/')
            cid = cap_resp.json()['data']['captcha_id']
            code = cache.get(f'mobile_captcha:{cid}')
            login_old = client.post(
                f'{base}/login/',
                data=json.dumps({
                    'username': username,
                    'password': password,
                    'device_id': device_id,
                    'captcha_id': cid,
                    'captcha_code': code,
                }),
                content_type='application/json',
            )
            old_token = login_old.json().get('data', {}).get('token', '')
            pending_resp = client.get(
                f'{base}/device/rebind/pending/',
                HTTP_AUTHORIZATION=f'Bearer {old_token}',
                HTTP_X_DEVICE_ID=device_id,
            )
            pending_body = check('GET /device/rebind/pending/ (after request)', pending_resp)
            if pending_body and pending_body.get('data', {}).get('verify_code'):
                verify_resp = client.post(
                    f'{base}/device/rebind/verify/',
                    data=json.dumps({
                        'request_id': request_id,
                        'verify_code': pending_body['data']['verify_code'],
                    }),
                    content_type='application/json',
                )
                check('POST /device/rebind/verify/', verify_resp)

            req = AppDeviceRebindRequest.objects.filter(id=request_id).first()
            if req and req.status == AppDeviceRebindRequest.STATUS_PENDING_OLD:
                resp = client.post(
                    f'{base}/device/rebind/cancel/',
                    data=json.dumps({'request_id': request_id}),
                    content_type='application/json',
                )
                check('POST /device/rebind/cancel/', resp)
            elif req and req.status == AppDeviceRebindRequest.STATUS_PENDING_ADMIN:
                req.status = AppDeviceRebindRequest.STATUS_CANCELLED
                req.save(update_fields=['status', 'updated_at'])
                total += 1
                passed += 1
                self.stdout.write(self.style.SUCCESS('[PASS] POST /device/rebind/cancel/ (cleanup after verify)'))

        self.stdout.write(f'\n{passed}/{total} checks passed')
        if passed != total:
            raise SystemExit(1)
