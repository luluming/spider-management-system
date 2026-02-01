from django.test import TestCase
from django.utils import timezone
from spiders.models import PSentiment, QusetAnswer


class DashboardStatsTests(TestCase):
    """Basic smoke tests for dashboard stats queries."""

    def test_dashboard_stats_queries_run(self):
        now = timezone.now()
        current_year = now.year

        # Create minimal sample data
        ps1 = PSentiment.objects.create(poiId='t_poi_1', p_time=now)
        QusetAnswer.objects.create(comment_id='c1', poiId='t_poi_1', release_time=now, comment_content='test')

        # 1) PSentiment POI list for current year
        year_pois = PSentiment.objects.filter(p_time__year=current_year).values_list('poiId', flat=True).distinct()
        year_poi_list = list(year_pois)
        self.assertIn('t_poi_1', year_poi_list)

        # 2) Associated comments count
        year_comments = QusetAnswer.objects.filter(
            poiId__in=year_poi_list,
            release_time__year__gte=2020,
            release_time__year__lte=2030,
        ).count()
        self.assertEqual(year_comments, 1)

        # 3) Ensure aggregated queries don't raise and return integers
        platforms = PSentiment.objects.filter(p_time__year=current_year).values('source_c').distinct()
        for p in platforms:
            # this should not raise
            _ = PSentiment.objects.filter(p_time__year=current_year, source_c=p.get('source_c')).count()

        all_pois = list(PSentiment.objects.values_list('poiId', flat=True).distinct())
        total_comments = QusetAnswer.objects.filter(
            poiId__in=all_pois,
            release_time__year__gte=2020,
            release_time__year__lte=2030
        ).count()
        self.assertIsInstance(total_comments, int)


