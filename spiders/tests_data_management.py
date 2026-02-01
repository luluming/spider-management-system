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
