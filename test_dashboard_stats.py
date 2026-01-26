#!/usr/bin/env python3
"""测试仪表板统计数据"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from spiders.models import PSentiment, QusetAnswer
from django.utils import timezone

# 获取当前时间信息
now = timezone.now()
current_year = now.year

print('=' * 70)
print('仪表板统计数据测试')
print('=' * 70)

# 1. PSentiment POI统计
print(f'\n1. PSentiment表 - 本年POI数量:')
year_pois = PSentiment.objects.filter(p_time__year=current_year).values_list('poiId', flat=True).distinct()
year_poi_list = list(year_pois)
print(f'   本年分析的POI数量: {len(year_poi_list)}')

# 按平台统计
print(f'\n   按平台分布:')
platforms = PSentiment.objects.filter(p_time__year=current_year).values('source_c').distinct()
for p in platforms:
    if p['source_c']:
        count = PSentiment.objects.filter(p_time__year=current_year, source_c=p['source_c']).count()
        print(f'     - {p["source_c"]}: {count} 个POI')

# 2. 关联的评论数据统计
print(f'\n2. 关联的评论数据 - 本年所有平台总计:')
year_comments = QusetAnswer.objects.filter(
    poiId__in=year_poi_list,
    release_time__year__gte=2020,
    release_time__year__lte=2030
).count()
print(f'   本年关联的评论总数: {year_comments:,} 条')

# 按平台统计评论数
print(f'\n   按平台的评论数分布:')
for p in platforms:
    if p['source_c']:
        platform_pois = list(PSentiment.objects.filter(
            p_time__year=current_year, 
            source_c=p['source_c']
        ).values_list('poiId', flat=True).distinct())
        
        comment_count = QusetAnswer.objects.filter(
            poiId__in=platform_pois,
            release_time__year__gte=2020,
            release_time__year__lte=2030
        ).count()
        print(f'     - {p["source_c"]}: {comment_count:,} 条评论')

# 3. 总计
print(f'\n3. 总体数据:')
all_pois = list(PSentiment.objects.values_list('poiId', flat=True).distinct())
total_comments = QusetAnswer.objects.filter(
    poiId__in=all_pois,
    release_time__year__gte=2020,
    release_time__year__lte=2030
).count()
print(f'   所有POI总数: {len(all_pois)}')
print(f'   关联评论总数: {total_comments:,} 条')

print(f'\n' + '=' * 70)
print('✅ 修改后的统计将显示评论数据量，更能反映真实数据规模')
print('=' * 70)


