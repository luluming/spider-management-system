from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model


class UIPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        User.objects.create_superuser('test_admin', 'test@example.com', 'TestPass123')
        self.client = Client()

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(reverse('data_management'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp.url)

    def test_dashboard_requires_login_and_renders(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)

        self.client.login(username='test_admin', password='TestPass123')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '仪表板')
        # stat card title from dashboard
        self.assertContains(resp, '总评论数')

    def test_data_management_renders_for_authenticated(self):
        self.client.login(username='test_admin', password='TestPass123')
        resp = self.client.get(reverse('data_management'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '配置管理')
        # check Alpine usage in migrated template
        self.assertContains(resp, 'x-data')

    def test_comments_list_reverse_exists(self):
        url = reverse('comments_list')
        resp = self.client.get(url)
        self.assertIn(resp.status_code, (200, 302))
