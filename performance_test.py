#!/usr/bin/env python
"""
性能测试脚本
Author: stone
"""

import os
import sys
import django
import time
import requests
from datetime import datetime

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from django.db.models import Q, Count, Avg, Sum
from spiders.models import QusetAnswer, PSentiment, SpiderBase

def test_database_queries():
    """测试数据库查询性能"""
    
    print("=" * 50)
    print("数据库查询性能测试")
    print("=" * 50)
    
    # 测试1: 基础统计查询
    print("\n1. 基础统计查询测试:")
    
    start_time = time.time()
    total_comments = QusetAnswer.objects.count()
    total_sentiment = PSentiment.objects.count()
    total_projects = SpiderBase.objects.count()
    end_time = time.time()
    
    print(f"   总评论数: {total_comments:,}")
    print(f"   总情感数据: {total_sentiment:,}")
    print(f"   总项目数: {total_projects:,}")
    print(f"   查询时间: {end_time - start_time:.3f}秒")
    
    # 测试2: 聚合查询
    print("\n2. 聚合查询测试:")
    
    start_time = time.time()
    comment_stats = QusetAnswer.objects.aggregate(
        total_likes=Sum('like_num'),
        total_replies=Sum('reply_num'),
        avg_rating=Avg('comment_grade')
    )
    end_time = time.time()
    
    print(f"   总点赞数: {comment_stats['total_likes'] or 0:,}")
    print(f"   总回复数: {comment_stats['total_replies'] or 0:,}")
    print(f"   平均评分: {comment_stats['avg_rating'] or 0:.2f}")
    print(f"   查询时间: {end_time - start_time:.3f}秒")
    
    # 测试3: 复杂筛选查询
    print("\n3. 复杂筛选查询测试:")
    
    start_time = time.time()
    # 模拟dashboard中的复杂查询
    sentiment_stats = PSentiment.objects.aggregate(
        today_count=Count('poiId', filter=Q(p_time__date=datetime.now().date())),
        month_count=Count('poiId', filter=Q(p_time__year=datetime.now().year, p_time__month=datetime.now().month)),
        total_count=Count('poiId')
    )
    end_time = time.time()
    
    print(f"   今日情感数据: {sentiment_stats['today_count']:,}")
    print(f"   本月情感数据: {sentiment_stats['month_count']:,}")
    print(f"   总情感数据: {sentiment_stats['total_count']:,}")
    print(f"   查询时间: {end_time - start_time:.3f}秒")
    
    # 测试4: 平台统计查询
    print("\n4. 平台统计查询测试:")
    
    start_time = time.time()
    platforms_data = PSentiment.objects.values('source_c').annotate(
        sentiment_count=Count('poiId'),
        project_count=Count('title', distinct=True)
    ).exclude(source_c__isnull=True).exclude(source_c='')[:5]  # 只测试前5个平台
    
    for platform_data in platforms_data:
        platform = platform_data['source_c']
        platform_poi_ids = PSentiment.objects.filter(source_c=platform).values_list('poiId', flat=True)
        comment_count = QusetAnswer.objects.filter(poiId__in=platform_poi_ids).count()
        
        print(f"   平台: {platform}")
        print(f"     情感数据: {platform_data['sentiment_count']:,}")
        print(f"     项目数: {platform_data['project_count']:,}")
        print(f"     评论数: {comment_count:,}")
    
    end_time = time.time()
    print(f"   查询时间: {end_time - start_time:.3f}秒")

def test_web_requests():
    """测试Web请求性能"""
    
    print("\n" + "=" * 50)
    print("Web请求性能测试")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    
    # 测试登录页面
    print("\n1. 登录页面加载测试:")
    start_time = time.time()
    try:
        response = requests.get(f"{base_url}/accounts/login/", timeout=10)
        end_time = time.time()
        print(f"   状态码: {response.status_code}")
        print(f"   响应时间: {end_time - start_time:.3f}秒")
        print(f"   响应大小: {len(response.content):,} 字节")
    except Exception as e:
        print(f"   请求失败: {e}")
    
    # 测试API接口
    print("\n2. API接口测试:")
    api_endpoints = [
        "/api/get_projects_by_platform/?platform=去哪儿",
        "/api/get_platform_stats/?platform=携程",
    ]
    
    for endpoint in api_endpoints:
        start_time = time.time()
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            end_time = time.time()
            print(f"   {endpoint}")
            print(f"     状态码: {response.status_code}")
            print(f"     响应时间: {end_time - start_time:.3f}秒")
        except Exception as e:
            print(f"   {endpoint} - 请求失败: {e}")

def test_cache_performance():
    """测试缓存性能"""
    
    print("\n" + "=" * 50)
    print("缓存性能测试")
    print("=" * 50)
    
    from django.core.cache import cache
    
    # 测试缓存写入
    print("\n1. 缓存写入测试:")
    test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
    
    start_time = time.time()
    cache.set("performance_test", test_data, 300)
    end_time = time.time()
    print(f"   缓存写入时间: {end_time - start_time:.6f}秒")
    
    # 测试缓存读取
    print("\n2. 缓存读取测试:")
    start_time = time.time()
    cached_data = cache.get("performance_test")
    end_time = time.time()
    print(f"   缓存读取时间: {end_time - start_time:.6f}秒")
    print(f"   缓存数据: {'命中' if cached_data else '未命中'}")

if __name__ == '__main__':
    print("数据管理系统性能测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 数据库查询测试
        test_database_queries()
        
        # 缓存性能测试
        test_cache_performance()
        
        # Web请求测试
        test_web_requests()
        
        print("\n" + "=" * 50)
        print("性能测试完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        sys.exit(1)
