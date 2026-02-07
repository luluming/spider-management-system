"""
定时任务：自动修复评论数据中的时间异常
将 release_time 超过当年或大于当前时间的记录修正为当前时间

使用方法（crontab 示例，每天凌晨2点执行）：
    0 2 * * * cd /opt/spider_management_system && python manage.py auto_fix_comment_anomalies

或 systemd timer 配置后运行：
    python manage.py auto_fix_comment_anomalies
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q

from spiders.models import QusetAnswer, PSentiment


class Command(BaseCommand):
    help = '自动修复评论数据中的时间异常（超过当年或未来时间）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅统计不实际修改',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        now = timezone.now()
        current_year = now.year

        valid_poi_ids = list(PSentiment.objects.values_list('poiId', flat=True).distinct())
        if not valid_poi_ids:
            self.stdout.write('无有效评论数据')
            return

        # 时间异常：年份超过当年 或 发布时间在未来
        queryset = QusetAnswer.objects.filter(
            poiId__in=valid_poi_ids
        ).filter(
            Q(release_time__year__gt=current_year) | Q(release_time__gt=now)
        )

        count = queryset.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS('未发现时间异常数据'))
            return

        if dry_run:
            self.stdout.write(f'[dry-run] 发现 {count} 条时间异常记录，将修正为当前时间')
            return

        updated = queryset.update(release_time=now)
        self.stdout.write(self.style.SUCCESS(f'已自动修正 {updated} 条时间异常记录'))
