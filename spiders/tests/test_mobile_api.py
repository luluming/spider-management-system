"""App Mobile API v1 集成测试"""
import json
from datetime import timedelta

from django.core.cache import cache
from django.test import Client, TestCase
from django.utils import timezone

from spiders.models import (
    AppCollector,
    AppCommentSubmission,
    AppDeviceRebindRequest,
    AppProjectPermission,
    AppAPIToken,
    QusetAnswer,
)
from spiders.mobile.utils import make_comment_id


class MobileAPITestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.base = '/api/v1/mobile'
        self.device_id = 'test-device-api-001'
        self.password = 'TestPass123'
        self.poi_id = 'test-poi-999'

        self.collector = AppCollector.objects.create(username='mobile_api_tester')
        self.collector.set_password(self.password)
        self.collector.bound_device_id = ''
        self.collector.save()

        AppProjectPermission.objects.create(
            collector=self.collector,
            poi_id=self.poi_id,
            item_name='测试项目',
            platform='测试平台',
            is_active=True,
        )

    def _get_captcha(self):
        resp = self.client.get(f'{self.base}/captcha/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        captcha_id = data['data']['captcha_id']
        captcha_code = cache.get(f'mobile_captcha:{captcha_id}')
        self.assertTrue(captcha_code)
        return captcha_id, captcha_code

    def _login(self, username=None, device_id=None):
        captcha_id, captcha_code = self._get_captcha()
        payload = {
            'username': username or self.collector.username,
            'password': self.password,
            'device_id': device_id or self.device_id,
            'device_info': 'pytest device',
            'captcha_id': captcha_id,
            'captcha_code': captcha_code,
        }
        resp = self.client.post(
            f'{self.base}/login/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        return resp

    def _auth_headers(self, token):
        return {
            'HTTP_AUTHORIZATION': f'Bearer {token}',
            'HTTP_X_DEVICE_ID': self.device_id,
        }

    def test_captcha(self):
        resp = self.client.get(f'{self.base}/captcha/')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertIn('captcha_id', body['data'])
        self.assertIn('captcha_image', body['data'])

    def test_login_logout_projects_flow(self):
        resp = self._login()
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['success'], body)
        token = body['data']['token']
        self.assertTrue(token)

        resp = self.client.get(f'{self.base}/projects/', **self._auth_headers(token))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['total_count'], 1)
        self.assertIsInstance(body['data'], list)
        self.assertEqual(len(body['data']), 1)
        self.assertEqual(body['data'][0]['poiId'], self.poi_id)
        self.assertEqual(body['projects'][0]['poiId'], self.poi_id)
        self.assertEqual(body['platforms'][0]['items'][0]['poiId'], self.poi_id)

        resp = self.client.post(f'{self.base}/logout/', **self._auth_headers(token))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        resp = self.client.get(f'{self.base}/projects/', **self._auth_headers(token))
        self.assertEqual(resp.status_code, 401)

    def test_comments_create_list_update(self):
        login_resp = self._login()
        token = login_resp.json()['data']['token']
        headers = self._auth_headers(token)

        now = timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')
        comment_payload = {
            'poiId': self.poi_id,
            'user_name': '测试用户',
            'comment_content': '集成测试评论内容',
            'comment_grade': '5',
            'comment_num': 5.0,
            'release_time': now,
        }
        resp = self.client.post(
            f'{self.base}/comments/',
            data=json.dumps(comment_payload),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['success'], body)
        comment_id = body['data']['comment']['comment_id']
        self.assertTrue(QusetAnswer.objects.filter(comment_id=comment_id).exists())
        self.assertTrue(AppCommentSubmission.objects.filter(comment_id=comment_id, collector=self.collector).exists())

        resp = self.client.get(f'{self.base}/comments/?poiId={self.poi_id}', **headers)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertGreaterEqual(body['data']['total'], 1)

        resp = self.client.get(f'{self.base}/comments/?poiId={self.poi_id}&mine=1', **headers)
        self.assertTrue(resp.json()['success'])

        update_payload = {'comment_content': '更新后的评论', 'like_num': 10}
        resp = self.client.put(
            f'{self.base}/comments/{comment_id}/',
            data=json.dumps(update_payload),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['success'])
        record = QusetAnswer.objects.get(comment_id=comment_id)
        self.assertEqual(record.comment_content, '更新后的评论')
        self.assertEqual(record.like_num, 10)

    def test_quset_answer_insert_alias(self):
        login_resp = self._login()
        token = login_resp.json()['data']['token']
        headers = self._auth_headers(token)
        resp = self.client.post(
            f'{self.base}/quset-answer/',
            data=json.dumps({
                'poiId': self.poi_id,
                'user_name': '别名接口用户',
                'comment_content': 'quset-answer 别名路径测试',
                'comment_grade': '4',
                'release_time': timezone.localtime().strftime('%Y-%m-%d %H:%M:%S'),
            }),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['success'], body)
        comment_id = body['data']['comment']['comment_id']
        self.assertTrue(QusetAnswer.objects.filter(comment_id=comment_id).exists())

    def test_comments_forbidden_poi(self):
        login_resp = self._login()
        token = login_resp.json()['data']['token']
        headers = self._auth_headers(token)

        resp = self.client.get(f'{self.base}/comments/?poiId=unauthorized-poi', **headers)
        self.assertEqual(resp.status_code, 403)

        resp = self.client.post(
            f'{self.base}/comments/',
            data=json.dumps({
                'poiId': 'unauthorized-poi',
                'user_name': 'x',
                'comment_content': 'y',
                'comment_grade': '1',
                'release_time': timezone.localtime().strftime('%Y-%m-%d %H:%M:%S'),
            }),
            content_type='application/json',
            **headers,
        )
        self.assertEqual(resp.status_code, 403)

    def test_device_mismatch(self):
        self.collector.bound_device_id = 'other-device'
        self.collector.save(update_fields=['bound_device_id'])

        resp = self._login(device_id='new-device-from-login')
        self.assertEqual(resp.status_code, 403)
        body = resp.json()
        self.assertFalse(body['success'])
        self.assertEqual(body['data']['error_code'], 'PENDING_ADMIN')
        self.assertEqual(body['data']['new_device_id'], 'new-device-from-login')
        req = AppDeviceRebindRequest.objects.get(id=body['data']['request_id'])
        self.assertEqual(req.status, AppDeviceRebindRequest.STATUS_PENDING_ADMIN)

    def test_rebind_flow(self):
        old_device = 'old-device-abc'
        new_device = 'new-device-xyz'
        self.collector.bound_device_id = old_device
        self.collector.save(update_fields=['bound_device_id'])

        captcha_id, captcha_code = self._get_captcha()
        resp = self.client.post(
            f'{self.base}/device/rebind/request/',
            data=json.dumps({
                'username': self.collector.username,
                'password': self.password,
                'device_id': new_device,
                'device_info': '新手机',
                'captcha_id': captcha_id,
                'captcha_code': captcha_code,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertTrue(body['success'], body)
        request_id = body['data']['request_id']

        login_resp = self._login(device_id=old_device)
        token = login_resp.json()['data']['token']
        resp = self.client.get(
            f'{self.base}/device/rebind/pending/',
            **self._auth_headers(token),
        )
        self.assertEqual(resp.status_code, 200)
        pending = resp.json()
        self.assertTrue(pending['success'])
        self.assertTrue(pending['data']['pending'])
        verify_code = pending['data']['verify_code']

        resp = self.client.post(
            f'{self.base}/device/rebind/verify/',
            data=json.dumps({'request_id': request_id, 'verify_code': verify_code}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['data']['status'], AppDeviceRebindRequest.STATUS_PENDING_ADMIN)

        req = AppDeviceRebindRequest.objects.get(id=request_id)
        req.status = AppDeviceRebindRequest.STATUS_APPROVED
        req.approved_expires_at = timezone.now() + timedelta(hours=2)
        req.save()

        resp = self.client.get(f'{self.base}/device/rebind/status/?request_id={request_id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['data']['status'], AppDeviceRebindRequest.STATUS_APPROVED)

        captcha_id, captcha_code = self._get_captcha()
        resp = self.client.post(
            f'{self.base}/device/rebind/complete/',
            data=json.dumps({
                'request_id': request_id,
                'username': self.collector.username,
                'password': self.password,
                'device_id': new_device,
                'device_info': '新手机',
                'captcha_id': captcha_id,
                'captcha_code': captcha_code,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()['success'])
        self.collector.refresh_from_db()
        self.assertEqual(self.collector.bound_device_id, new_device)

    def test_rebind_cancel(self):
        self.collector.bound_device_id = 'old-dev'
        self.collector.save(update_fields=['bound_device_id'])

        captcha_id, captcha_code = self._get_captcha()
        resp = self.client.post(
            f'{self.base}/device/rebind/request/',
            data=json.dumps({
                'username': self.collector.username,
                'password': self.password,
                'device_id': 'new-dev-cancel',
                'captcha_id': captcha_id,
                'captcha_code': captcha_code,
            }),
            content_type='application/json',
        )
        request_id = resp.json()['data']['request_id']

        resp = self.client.post(
            f'{self.base}/device/rebind/cancel/',
            data=json.dumps({'request_id': request_id}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])
        req = AppDeviceRebindRequest.objects.get(id=request_id)
        self.assertEqual(req.status, AppDeviceRebindRequest.STATUS_CANCELLED)

    def test_comment_id_generation(self):
        cid = make_comment_id('用户A', '5', '内容测试')
        self.assertEqual(len(cid), 32)
