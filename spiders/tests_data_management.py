from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from .models import SpiderBase, PSentiment, QusetAnswer
import json


class DataManagementAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user('dm_user', 'dm@example.com', 'pass')
        self.user.is_staff = True
        self.user.save()
        self.client.login(username='dm_user', password='pass')

    def test_add_spider_same_name_different_platforms(self):
        SpiderBase.objects.create(
            IteamName='深圳世界之窗',
            SalesChannel='去哪儿',
            request_data='{}',
            project_id='qunar-1',
        )
        resp = self.client.post('/add-spider/', {
            'IteamName': '深圳世界之窗',
            'SalesChannel': '抖音',
            'request_data': '{}',
            'project_id': 'dy-1',
        })
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'), data.get('message'))

    def test_add_spider_duplicate_same_platform_rejected(self):
        SpiderBase.objects.create(
            IteamName='深圳世界之窗',
            SalesChannel='抖音',
            request_data='{}',
            project_id='dy-1',
        )
        resp = self.client.post('/add-spider/', {
            'IteamName': '深圳世界之窗',
            'SalesChannel': '抖音',
            'request_data': '{}',
            'project_id': 'dy-2',
        })
        data = json.loads(resp.content)
        self.assertFalse(data.get('success'))
        self.assertIn('抖音', data.get('message', ''))

    def test_add_and_get_spider(self):
        # Add spider via API
        resp = self.client.post('/add-spider/', {
            'IteamName': 'Test Project A',
            'SalesChannel': 'TestPlatform',
            'industry': 'TestIndustry',
            'request_data': '{"url":"http://example.com"}',
            'project_id': 'proj-123',
            'IteamState': 'active',
            'poid': '1001',
            'sort_type': '1'
        })
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        spider_id = data.get('spider_id')
        self.assertIsNotNone(spider_id)

        # Get spider detail
        resp2 = self.client.get(f'/get-spider-detail/{spider_id}/')
        data2 = json.loads(resp2.content)
        self.assertTrue(data2.get('success'))
        self.assertEqual(data2['spider']['IteamName'], 'Test Project A')

    def test_edit_spider(self):
        # create a spider and edit it
        sb = SpiderBase.objects.create(IteamName='Old Name', SalesChannel='OldChannel', request_data='{}', project_id='old-proj')
        resp = self.client.post(f'/edit-spider/{sb.id}/', {
            'IteamName': 'New Name',
            'SalesChannel': 'NewChannel',
            'industry': 'NewIndustry',
            'request_data': '{"url":"http://x"}',
            'project_id': 'new-proj',
            'IteamState': 'inactive',
            'poid': '2002',
            'sort_type': '2'
        })
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        sb.refresh_from_db()
        self.assertEqual(sb.IteamName, 'New Name')
        self.assertEqual(sb.SalesChannel, 'NewChannel')

    def test_toggle_spider_status(self):
        sb = SpiderBase.objects.create(
            IteamName='Toggle Test',
            SalesChannel='抖音',
            request_data='{}',
            project_id='tog-1',
            IteamState='active',
        )
        self.assertTrue(sb.is_config_active)
        resp = self.client.post(f'/toggle-spider-status/{sb.id}/')
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'), data.get('message'))
        self.assertFalse(data.get('is_active'))
        self.assertEqual(data.get('state_label'), '关闭')
        sb.refresh_from_db()
        self.assertEqual(sb.IteamState, 'inactive')
        resp2 = self.client.post(f'/toggle-spider-status/{sb.id}/')
        data2 = json.loads(resp2.content)
        self.assertTrue(data2.get('is_active'))
        self.assertEqual(data2.get('state_label'), '激活')

    def test_delete_spider(self):
        sb = SpiderBase.objects.create(IteamName='ToDelete', SalesChannel='DelChannel', request_data='{}', project_id='pdel')
        resp = self.client.post(f'/delete-spider/{sb.id}/')
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        self.assertFalse(SpiderBase.objects.filter(id=sb.id).exists())

    def test_get_projects_endpoint(self):
        # Ensure projects list is returned for a platform
        now = timezone.now()
        PSentiment.objects.create(poiId='poi-p1', source_c='P1', title='Proj-A', p_time=now)
        PSentiment.objects.create(poiId='poi-p2', source_c='P1', title='Proj-B', p_time=now)

        resp = self.client.get('/get-projects-by-platform/?platform=P1')
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        self.assertIn('projects', data)
        self.assertIn('Proj-A', data['projects'])
        self.assertIn('Proj-B', data['projects'])

    def test_get_statistics_endpoint(self):
        # Create test sentiment and comments and ask for statistics
        now = timezone.now()
        poi = 'poi-stat-1'
        PSentiment.objects.create(poiId=poi, source_c='SP', title='MyProj', p_time=now)
        QusetAnswer.objects.create(comment_id='cs1', poiId=poi, release_time=now, comment_content='ok', like_num=3, reply_num=1, comment_grade=4.5)

        resp = self.client.get('/get-statistics/?platform=SP&project=MyProj')
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        stats = data.get('statistics') or {}
        self.assertIn('total_comments', stats)
        self.assertGreaterEqual(stats['total_comments'], 1)

    def test_platform_trend_endpoints(self):
        # Create PSentiment and related QusetAnswer data
        now = timezone.now()
        poi = 'poi-td-1'
        ps = PSentiment.objects.create(poiId=poi, source_c='TP', title='TP-1', p_time=now)
        QusetAnswer.objects.create(comment_id='c-1', poiId=poi, release_time=now, comment_content='ok')

        # Monthly trends
        resp = self.client.get('/get-platform-monthly-trends/')
        data = json.loads(resp.content)
        self.assertTrue(data.get('success'))
        self.assertIn('platforms', data)
        self.assertIn('months', data)

        # Daily project trends
        resp2 = self.client.get('/get-platform-project-daily-trends/')
        data2 = json.loads(resp2.content)
        if not data2.get('success'):
            self.fail(f"get-platform-project-daily-trends failed: {data2}")
        self.assertIn('platform_project_trends', data2)
        self.assertIn('dates', data2)

    def test_basic_table_sort_by_reply_num(self):
        now = timezone.now()
        PSentiment.objects.create(poiId='sort-low', source_c='抖音', title='低评论', reply_num=5, comment_num='4.0', p_time=now)
        PSentiment.objects.create(poiId='sort-high', source_c='抖音', title='高评论', reply_num=500, comment_num='4.5', p_time=now)

        resp = self.client.get('/basic-table-query/', {
            'sort_by': 'reply_num',
            'order': 'desc',
            'page_size': 20,
        })
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('sort-high', content)
        self.assertIn('sort-low', content)
        self.assertLess(content.index('sort-high'), content.index('sort-low'))
        self.assertIn('fa-sort-down', content)

    def test_basic_table_sort_links_in_template(self):
        now = timezone.now()
        PSentiment.objects.create(poiId='sort-link', source_c='抖音', title='链接测试', reply_num=1, comment_num='3.0', p_time=now)
        resp = self.client.get('/basic-table-query/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'sort_by=comment_num')
        self.assertContains(resp, 'sort_by=reply_num')
