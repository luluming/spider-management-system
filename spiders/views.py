from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .decorators import require_permission, permission_required_or_json
from django.utils.decorators import method_decorator
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
import json
import csv
import xlsxwriter
import random
import time
from io import BytesIO
from .models import QusetAnswer, SpiderBase, PSentiment, UserProjectPermission, MobileAPIToken
from datetime import timedelta
from accounts.models import OperationLog
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
import secrets
import hashlib


def get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@login_required
def dashboard(request):
    """主页仪表板 - 基于p_sentiment和quset_answer表的联合统计"""
    # 记录查看数据操作
    OperationLog.objects.create(
        user=request.user,
        operation='查看仪表板',
        action='view_data',
        target='仪表板',
        description='访问主页仪表板',
        ip_address=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # 获取当前时间信息
    now = timezone.now()
    today = now.date()
    current_year = now.year
    current_month = now.month
    
    # 使用缓存键
    cache_key = f"dashboard_stats_{today}_{current_year}_{current_month}"
    cached_stats = cache.get(cache_key)
    
    if cached_stats:
        return render(request, 'spiders/dashboard.html', cached_stats)
    
    # === PSentiment表统计 - 批量查询优化 ===
    # 使用单个查询获取所有统计数据
    sentiment_stats = PSentiment.objects.aggregate(
        today_count=Count('poiId', filter=Q(p_time__date=today)),
        month_count=Count('poiId', filter=Q(p_time__year=current_year, p_time__month=current_month)),
        year_count=Count('poiId', filter=Q(p_time__year=current_year)),
        total_count=Count('poiId')
    )
    
    # PSentiment的POI数量（用于其他地方）
    today_sentiment_pois = sentiment_stats['today_count']
    month_sentiment_pois = sentiment_stats['month_count']
    year_sentiment_pois = sentiment_stats['year_count']
    total_sentiment_pois = sentiment_stats['total_count']
    
    # 获取对应的poiId列表，用于关联评论数据
    today_poi_ids = list(PSentiment.objects.filter(p_time__date=today).values_list('poiId', flat=True).distinct())
    month_poi_ids = list(PSentiment.objects.filter(p_time__year=current_year, p_time__month=current_month).values_list('poiId', flat=True).distinct())
    year_poi_ids = list(PSentiment.objects.filter(p_time__year=current_year).values_list('poiId', flat=True).distinct())
    all_poi_ids = list(PSentiment.objects.values_list('poiId', flat=True).distinct())
    
    # 统计关联的评论数据量（同时限制评论的时间范围和过滤异常年份）
    today_sentiment = QusetAnswer.objects.filter(
        poiId__in=today_poi_ids,
        release_time__date=today,  # 只统计今天的评论
        release_time__year__gte=2020,
        release_time__year__lte=2030
    ).count() if today_poi_ids else 0
    
    month_sentiment = QusetAnswer.objects.filter(
        poiId__in=month_poi_ids,
        release_time__year=current_year,  # 只统计本年的评论
        release_time__month=current_month,  # 只统计本月的评论
        release_time__year__gte=2020,
        release_time__year__lte=2030
    ).count() if month_poi_ids else 0
    
    year_sentiment = QusetAnswer.objects.filter(
        poiId__in=year_poi_ids,
        release_time__year=current_year,  # 只统计本年的评论
        release_time__year__gte=2020,
        release_time__year__lte=2030
    ).count() if year_poi_ids else 0
    
    # 所有POI关联的评论总数（过滤异常年份）
    total_sentiment = QusetAnswer.objects.filter(
        poiId__in=all_poi_ids,
        release_time__year__gte=2020,
        release_time__year__lte=2030
    ).count() if all_poi_ids else 0
    
    # === QusetAnswer表统计 - 批量查询优化 ===
    comment_stats = QusetAnswer.objects.aggregate(
        today_count=Count('comment_id', filter=Q(release_time__date=today)),
        month_count=Count('comment_id', filter=Q(release_time__year=current_year, release_time__month=current_month)),
        year_count=Count('comment_id', filter=Q(release_time__year=current_year)),
        total_count=Count('comment_id'),
        total_likes=Sum('like_num'),
        total_replies=Sum('reply_num')
    )
    
    today_comments = comment_stats['today_count']
    month_comments = comment_stats['month_count']
    year_comments = comment_stats['year_count']
    total_comments = comment_stats['total_count']
    total_likes = comment_stats['total_likes'] or 0
    total_replies = comment_stats['total_replies'] or 0
    
    # 优化活跃用户统计
    active_users = QusetAnswer.objects.values('user_name').distinct().count()
    
    # === 平台统计（基于PSentiment表）- 优化查询 ===
    platform_stats = []
    # 使用缓存获取平台统计数据
    platform_cache_key = f"platform_stats_{today}"
    platform_stats = cache.get(platform_cache_key)
    
    if not platform_stats:
        # 批量查询平台数据
        platforms_data = PSentiment.objects.values('source_c').annotate(
            sentiment_count=Count('poiId'),
            project_count=Count('title', distinct=True)
        ).exclude(source_c__isnull=True).exclude(source_c='')
        
        # 批量获取每个平台的评论统计
        platform_stats = []
        for platform_data in platforms_data:
            platform = platform_data['source_c']
            platform_poi_ids = PSentiment.objects.filter(source_c=platform).values_list('poiId', flat=True)
            
            # 批量统计评论数据
            comment_stats = QusetAnswer.objects.filter(poiId__in=platform_poi_ids).aggregate(
                comment_count=Count('comment_id'),
                avg_likes=Avg('like_num'),
                avg_replies=Avg('reply_num')
            )
            
            platform_stats.append({
                'platform': platform,
                'sentiment_count': platform_data['sentiment_count'],
                'comment_count': comment_stats['comment_count'],
                'project_count': platform_data['project_count'],
                'avg_likes': comment_stats['avg_likes'] or 0,
                'avg_replies': comment_stats['avg_replies'] or 0,
            })
        
        platform_stats.sort(key=lambda x: x['sentiment_count'], reverse=True)
        # 缓存平台统计数据
        cache.set(platform_cache_key, platform_stats, 300)
    
    # === 月度增长趋势（最近12个月）- 优化查询 ===
    monthly_cache_key = f"monthly_growth_{current_year}_{current_month}"
    monthly_growth = cache.get(monthly_cache_key)
    
    if not monthly_growth:
        # 批量查询最近12个月的数据
        monthly_data = []
        for i in range(12):
            month_date = now - timedelta(days=30 * i)
            monthly_data.append((month_date.year, month_date.month))
        
        # 批量查询所有月份的数据
        sentiment_monthly = PSentiment.objects.values('p_time__year', 'p_time__month').annotate(
            count=Count('poiId')
        ).filter(
            p_time__year__in=[month[0] for month in monthly_data],
            p_time__month__in=[month[1] for month in monthly_data]
        )
        
        comment_monthly = QusetAnswer.objects.values('release_time__year', 'release_time__month').annotate(
            count=Count('comment_id')
        ).filter(
            release_time__year__in=[month[0] for month in monthly_data],
            release_time__month__in=[month[1] for month in monthly_data]
        )
        
        # 创建查找字典
        sentiment_dict = {(item['p_time__year'], item['p_time__month']): item['count'] for item in sentiment_monthly}
        comment_dict = {(item['release_time__year'], item['release_time__month']): item['count'] for item in comment_monthly}
        
        monthly_growth = []
        for year, month in monthly_data:
            monthly_growth.append({
                'month': f"{year}-{month:02d}",
                'sentiment_count': sentiment_dict.get((year, month), 0),
                'comment_count': comment_dict.get((year, month), 0)
            })
        
        monthly_growth.reverse()  # 按时间正序
        cache.set(monthly_cache_key, monthly_growth, 600)  # 缓存10分钟
    
    # === 每日增长趋势（最近30天）- 优化查询 ===
    daily_cache_key = f"daily_growth_{today}"
    daily_growth = cache.get(daily_cache_key)
    
    if not daily_growth:
        # 批量查询最近30天的数据
        daily_dates = [today - timedelta(days=i) for i in range(30)]
        
        # 批量查询所有日期的数据
        sentiment_daily = PSentiment.objects.values('p_time__date').annotate(
            count=Count('poiId')
        ).filter(p_time__date__in=daily_dates)
        
        comment_daily = QusetAnswer.objects.values('release_time__date').annotate(
            count=Count('comment_id')
        ).filter(release_time__date__in=daily_dates)
        
        # 创建查找字典
        sentiment_dict = {item['p_time__date']: item['count'] for item in sentiment_daily}
        comment_dict = {item['release_time__date']: item['count'] for item in comment_daily}
        
        daily_growth = []
        for day_date in daily_dates:
            daily_growth.append({
                'date': day_date.strftime('%Y-%m-%d'),
                'sentiment_count': sentiment_dict.get(day_date, 0),
                'comment_count': comment_dict.get(day_date, 0)
            })
        
        daily_growth.reverse()  # 按时间正序
        cache.set(daily_cache_key, daily_growth, 300)  # 缓存5分钟
    
    context = {
        # 基础统计
        'total_comments': total_comments,
        'total_sentiment': total_sentiment,
        'total_likes': total_likes,
        'total_replies': total_replies,
        'active_users': active_users,
        
        # 今日统计
        'today_sentiment': today_sentiment,
        'today_comments': today_comments,
        
        # 时间统计
        'month_sentiment': month_sentiment,
        'month_comments': month_comments,
        'year_sentiment': year_sentiment,
        'year_comments': year_comments,
        
        # 平台统计
        'platform_stats': platform_stats,
        
        # 趋势数据（JSON格式用于图表）
        'monthly_growth': json.dumps(monthly_growth),
        'daily_growth': json.dumps(daily_growth),
        
        # 平台分布数据 - 基于quset_answer表的评论数据
        'platform_distribution': json.dumps([{
            'platform': stat['platform'],
            'count': stat['comment_count']
        } for stat in platform_stats]),
    }
    
    # 缓存完整的dashboard数据
    cache.set(cache_key, context, 300)  # 缓存5分钟
    
    return render(request, 'spiders/dashboard.html', context)


@login_required
def get_platform_monthly_trends(request):
    """获取按平台分色的月度数据增长趋势"""
    try:
        # 获取当前时间
        now = timezone.now()
        current_year = now.year
        current_month = now.month
        
        # 计算最近12个月
        monthly_data = []
        for i in range(12):
            month_date = now - timedelta(days=30 * i)
            monthly_data.append((month_date.year, month_date.month))
        
        monthly_data.reverse()  # 按时间正序
        
        # 获取所有平台
        platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='')
        
        # 为每个平台生成颜色
        colors = [
            '#2563eb', '#10b981', '#f59e0b', '#ef4444',
            '#8b5cf6', '#06b6d4', '#84cc16', '#f97316',
            '#ec4899', '#14b8a6', '#f97316', '#6366f1'
        ]
        
        platform_trends = []
        for i, platform in enumerate(platforms):
            # 1. 先获取该平台的所有poiId
            platform_poi_ids = list(PSentiment.objects.filter(source_c=platform).values_list('poiId', flat=True))
            
            if not platform_poi_ids:
                continue
            
            # 2. 根据poiId到quset_answer表查询每个月的评论数据
            # 使用Django ORM而不是extra()，更安全且跨数据库
            platform_monthly_data = []
            for year, month in monthly_data:
                # 计算该月的开始和结束日期
                if month == 12:
                    next_year, next_month = year + 1, 1
                else:
                    next_year, next_month = year, month + 1
                
                start_date = timezone.datetime(year, month, 1, tzinfo=timezone.utc)
                end_date = timezone.datetime(next_year, next_month, 1, tzinfo=timezone.utc)
                
                # 查询该月的数据，添加年份限制避免异常数据
                count = QusetAnswer.objects.filter(
                    poiId__in=platform_poi_ids,
                    release_time__gte=start_date,
                    release_time__lt=end_date,
                    release_time__year__gte=2020,  # 添加合理年份限制
                    release_time__year__lte=2030
                ).count()
                
                platform_monthly_data.append({
                    'month': f"{year}-{month:02d}",
                    'count': count
                })
            
            # 只保留有数据的平台
            total_count = sum(item['count'] for item in platform_monthly_data)
            if total_count > 0:
                platform_trends.append({
                    'platform': platform,
                    'data': platform_monthly_data,
                    'color': colors[i % len(colors)],
                    'total_count': total_count
                })
        
        # 按总数据量排序
        platform_trends.sort(key=lambda x: x['total_count'], reverse=True)
        
        # 生成月份标签
        month_labels = [f"{year}-{month:02d}" for year, month in monthly_data]
        
        return JsonResponse({
            'success': True,
            'platforms': platform_trends,
            'months': month_labels
        })
        
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@login_required
def get_platform_project_daily_trends(request):
    """获取按平台和项目分组的每日数据增长趋势"""
    try:
        # 获取参数
        platform = request.GET.get('platform', '')
        project = request.GET.get('project', '')
        
        # 获取当前时间
        now = timezone.now()
        today = now.date()
        
        # 计算最近30天
        daily_dates = [today - timedelta(days=i) for i in range(30)]
        daily_dates.reverse()  # 按时间正序
        
        # 获取所有平台和项目
        if platform and project:
            # 指定平台和项目
            platform_poi_ids = PSentiment.objects.filter(
                source_c=platform, 
                title=project
            ).values_list('poiId', flat=True)
        elif platform:
            # 指定平台的所有项目
            platform_poi_ids = PSentiment.objects.filter(
                source_c=platform
            ).values_list('poiId', flat=True)
        else:
            # 所有平台和项目
            platform_poi_ids = PSentiment.objects.values_list('poiId', flat=True)
        
        if not platform_poi_ids:
            return JsonResponse({
                'success': True,
                'platform_project_trends': [],
                'dates': [date.strftime('%Y-%m-%d') for date in daily_dates]
            })
        
        # 为每个平台和项目生成颜色
        colors = [
            '#2563eb', '#10b981', '#f59e0b', '#ef4444',
            '#8b5cf6', '#06b6d4', '#84cc16', '#f97316',
            '#ec4899', '#14b8a6', '#f97316', '#6366f1'
        ]
        
        # 获取平台项目组合
        if platform and project:
            # 单个平台项目
            platform_projects = [{'platform': platform, 'project': project}]
        elif platform:
            # 指定平台的所有项目
            platform_projects = PSentiment.objects.filter(
                source_c=platform
            ).values('source_c', 'title').distinct()
        else:
            # 所有平台的前10个项目（按数据量排序）
            platform_projects = PSentiment.objects.values('source_c', 'title').annotate(
                count=Count('poiId')
            ).order_by('-count')[:10]
        
        platform_project_trends = []
        for i, pp in enumerate(platform_projects):
            if isinstance(pp, dict):
                # 检查字典中是否有platform键（手动创建的字典）
                if 'platform' in pp:
                    platform_name = pp['platform']
                    project_name = pp['project']
                else:
                    # values()返回的字典使用source_c和title键
                    platform_name = pp['source_c']
                    project_name = pp['title']
            else:
                platform_name = pp.source_c
                project_name = pp.title
            
            # 获取该平台项目的poiId
            if platform and project:
                pp_poi_ids = list(platform_poi_ids)
            else:
                pp_poi_ids = PSentiment.objects.filter(
                    source_c=platform_name,
                    title=project_name
                ).values_list('poiId', flat=True)
            
            if not pp_poi_ids:
                continue
            
            # 查询每日数据（使用ORM以保证跨数据库兼容性）
            # 注意：避免使用数据库特定的 YEAR() 函数，使用 release_time__date 进行日期匹配
            daily_queryset = QusetAnswer.objects.filter(
                poiId__in=pp_poi_ids,
                release_time__date__in=[d for d in daily_dates],
                release_time__year__gte=2020,
                release_time__year__lte=2030
            ).values('release_time__date').annotate(count=Count('comment_id'))

            # 兼容不同 DB 返回的键名
            daily_dict = {}
            for item in daily_queryset:
                key = item.get('release_time__date') or item.get('date')
                if hasattr(key, 'strftime'):
                    key = key.strftime('%Y-%m-%d')
                daily_dict[key] = item['count']
            
            # 构建该平台项目的数据
            pp_data = []
            for date in daily_dates:
                pp_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'count': daily_dict.get(date, 0)
                })
            
            platform_project_trends.append({
                'platform': platform_name,
                'project': project_name,
                'data': pp_data,
                'color': colors[i % len(colors)],
                'total_count': sum(item['count'] for item in pp_data)
            })
        
        # 按总数据量排序
        platform_project_trends.sort(key=lambda x: x['total_count'], reverse=True)
        
        return JsonResponse({
            'success': True,
            'platform_project_trends': platform_project_trends,
            'dates': [date.strftime('%Y-%m-%d') for date in daily_dates]
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def _get_last_nonempty_get(request, key, default=''):
    """取 QueryDict 中该键最后一次出现的非空值（避免 sort_by=a&sort_by= 时 .get 得到空串）。"""
    for val in reversed(request.GET.getlist(key)):
        s = (val or '').strip()
        if s:
            return s
    return default


def _parse_comments_page_size(request, default=20, max_size=500):
    """解析每页条数：支持重复 key，忽略空段，避免 int('') 导致 500。"""
    for raw in reversed(request.GET.getlist('page_size')):
        s = (raw or '').strip()
        if not s:
            continue
        try:
            n = int(s)
            return max(1, min(n, max_size))
        except (TypeError, ValueError):
            continue
    return default


@login_required
def comments_list(request):
    """评论列表页面 - 基于QusetAnswer表显示，通过PSentiment表的poiId关联"""
    # 获取筛选参数
    platform = request.GET.get('platform', '')
    project = request.GET.get('project', '')
    
    start_date = request.GET.get('start_date', "")
    end_date = request.GET.get('end_date', '')
    
    rating = request.GET.get('rating', '')
    keyword = request.GET.get('keyword', '')
    sort_by = _get_last_nonempty_get(request, 'sort_by', '-release_time')
    page_size = _parse_comments_page_size(request)
    
    # 如果没有选择平台或项目，返回空结果，避免显示过多数据
    if not platform and not project:
        queryset = QusetAnswer.objects.none()
    else:
        # 构建查询 - 基于QusetAnswer表，通过注释添加PSentiment表字段
        # 只查询在PSentiment表中有记录的poiId对应的评论
        valid_poi_ids = PSentiment.objects.values_list('poiId', flat=True).distinct()
        queryset = QusetAnswer.objects.filter(poiId__in=valid_poi_ids).extra(
            select={
                'project_title': """
                    SELECT title FROM p_sentiment p 
                    WHERE p.poiId = quset_answer.poiId 
                    LIMIT 1
                """,
                'platform_source_c': """
                    SELECT source_c FROM p_sentiment p 
                    WHERE p.poiId = quset_answer.poiId 
                    LIMIT 1
                """
            }
        )
        
        # 添加日期筛选 - 使用extra()避免release_time__date的bug
        if start_date or end_date:
            where_conditions = []
            params = []
            
            if start_date:
                where_conditions.append('DATE(release_time) >= %s')
                params.append(start_date)
            
            if end_date:
                where_conditions.append('DATE(release_time) <= %s')
                params.append(end_date)
            
            if where_conditions:
                queryset = queryset.extra(where=where_conditions, params=params)
        
        # 通过PSentiment表进一步筛选评论
        sentiment_filter = PSentiment.objects.all()
        
        if platform:
            sentiment_filter = sentiment_filter.filter(source_c=platform)
        
        if project:
            sentiment_filter = sentiment_filter.filter(title__icontains=project)
        
        # 获取符合条件的poiId列表
        filtered_poi_ids = sentiment_filter.values_list('poiId', flat=True)
        filtered_poi_ids_list = list(filtered_poi_ids)
        
        if filtered_poi_ids_list:
            queryset = queryset.filter(poiId__in=filtered_poi_ids_list)
        else:
            queryset = queryset.none()  # 如果没有匹配的poiId，返回空查询集
    
    
    # 评分筛选 - 使用评论表的comment_grade
    if rating:
        queryset = queryset.filter(comment_grade=rating)
    
    # 关键词搜索 - 使用评论表的字段
    if keyword:
        queryset = queryset.filter(
            Q(user_name__icontains=keyword) | 
            Q(comment_content__icontains=keyword)
        )
    
    # 排序 - 调整排序字段（现在基于QusetAnswer表）
    if sort_by == '-publishTime':
        sort_by = '-release_time'  # QusetAnswer表的release_time字段
    elif sort_by == '-rating':
        sort_by = '-comment_grade'
    elif sort_by == '-likeCount':
        sort_by = '-like_num'
    elif sort_by == '-replyCount':
        sort_by = '-reply_num'

    allowed_sort = (
        'release_time',
        '-release_time',
        'comment_grade',
        '-comment_grade',
        'like_num',
        '-like_num',
        'reply_num',
        '-reply_num',
    )
    if sort_by not in allowed_sort:
        sort_by = '-release_time'

    queryset = queryset.order_by(sort_by)
    
    # 分页
    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 获取平台列表 - 使用PSentiment表
    platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='').order_by('source_c')
    
    # 获取项目列表（如果选择了平台）
    projects = []
    if platform:
        projects = PSentiment.objects.filter(source_c=platform).values_list('title', flat=True).distinct().exclude(title__isnull=True).exclude(title='').order_by('title')
    
    context = {
        'page_obj': page_obj,
        'platforms': platforms,
        'projects': projects,
        'sort_by': sort_by,
        'current_filters': {
            'platform': platform,
            'project': project,
            'start_date': start_date,
            'end_date': end_date,
            'rating': rating,
            'keyword': keyword,
            'sort_by': sort_by,
            'page_size': page_size,
        }
    }
    
    # 如果是AJAX请求，只返回评论列表内容（与主页面保持一致使用tailwind模板）
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(
            request,
            'spiders/comments_list_content_tailwind.html',
            {'page_obj': page_obj, 'sort_by': sort_by},
        )
    
    return render(request, 'spiders/comments_list.html', context)


@login_required
def comment_anomaly_check(request):
    """评论数据异常检查 - 显示1分评分、差评、时间异常等，支持修改和删除"""
    platform = request.GET.get('platform', '')
    project = request.GET.get('project', '')
    anomaly_types = request.GET.getlist('anomaly_type')  # 可多选: rating_1, negative, time_abnormal
    page_size = _parse_comments_page_size(request)

    # 基础查询：只查询在PSentiment中有记录的评论
    valid_poi_ids = PSentiment.objects.values_list('poiId', flat=True).distinct()
    queryset = QusetAnswer.objects.filter(poiId__in=valid_poi_ids).extra(
        select={
            'project_title': """
                SELECT title FROM p_sentiment p 
                WHERE p.poiId = quset_answer.poiId 
                LIMIT 1
            """,
            'platform_source_c': """
                SELECT source_c FROM p_sentiment p 
                WHERE p.poiId = quset_answer.poiId 
                LIMIT 1
            """
        }
    )

    # 平台/项目筛选
    if platform or project:
        sentiment_filter = PSentiment.objects.all()
        if platform:
            sentiment_filter = sentiment_filter.filter(source_c=platform)
        if project:
            sentiment_filter = sentiment_filter.filter(title__icontains=project)
        filtered_poi_ids = list(sentiment_filter.values_list('poiId', flat=True))
        if filtered_poi_ids:
            queryset = queryset.filter(poiId__in=filtered_poi_ids)
        else:
            queryset = queryset.none()

    # 异常分类筛选：category=time_abnormal | rating_1 | negative | ''(全部)
    now = timezone.now()
    current_year = now.year
    category = request.GET.get('category', '')
    base_anomaly = Q(comment_grade__lte=2) | Q(release_time__year__gt=current_year) | Q(release_time__gt=now)
    queryset = queryset.filter(base_anomaly)

    if category == 'time_abnormal':
        queryset = queryset.filter(Q(release_time__year__gt=current_year) | Q(release_time__gt=now))
    elif category == 'rating_1':
        queryset = queryset.filter(Q(comment_grade=1) | Q(comment_grade=1.0))
    elif category == 'negative':
        queryset = queryset.filter(Q(comment_grade__lte=2) & ~Q(comment_grade=1) & ~Q(comment_grade=1.0))  # 2星差评
    elif anomaly_types:
        q_anomaly = Q()
        if 'rating_1' in anomaly_types:
            q_anomaly |= Q(comment_grade=1) | Q(comment_grade=1.0)
        if 'negative' in anomaly_types:
            q_anomaly |= Q(comment_grade__lte=2)
        if 'time_abnormal' in anomaly_types:
            q_anomaly |= Q(release_time__year__gt=current_year) | Q(release_time__gt=now)
        if q_anomaly:
            queryset = queryset.filter(q_anomaly)

    queryset = queryset.order_by('-release_time')

    # 分类统计（在当前平台/项目筛选下的数量）
    base_qs = QusetAnswer.objects.filter(poiId__in=valid_poi_ids)
    if platform or project:
        sentiment_filter = PSentiment.objects.all()
        if platform:
            sentiment_filter = sentiment_filter.filter(source_c=platform)
        if project:
            sentiment_filter = sentiment_filter.filter(title__icontains=project)
        fpids = list(sentiment_filter.values_list('poiId', flat=True))
        base_qs = base_qs.filter(poiId__in=fpids) if fpids else base_qs.none()
    base_anomaly_qs = base_qs.filter(base_anomaly)
    stats = {
        'time_abnormal': base_anomaly_qs.filter(Q(release_time__year__gt=current_year) | Q(release_time__gt=now)).count(),
        'rating_1': base_anomaly_qs.filter(Q(comment_grade=1) | Q(comment_grade=1.0)).count(),
        'negative': base_anomaly_qs.filter(Q(comment_grade__lte=2) & ~Q(comment_grade=1) & ~Q(comment_grade=1.0)).count(),
    }

    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='').order_by('source_c')
    projects = []
    if platform:
        projects = PSentiment.objects.filter(source_c=platform).values_list('title', flat=True).distinct().exclude(title__isnull=True).exclude(title='').order_by('title')

    context = {
        'page_obj': page_obj,
        'platforms': platforms,
        'projects': projects,
        'stats': stats,
        'current_filters': {
            'platform': platform,
            'project': project,
            'category': category,
            'anomaly_types': anomaly_types,
            'page_size': page_size,
        }
    }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'spiders/comment_anomaly_content.html', {'page_obj': page_obj})

    return render(request, 'spiders/comment_anomaly_check.html', context)


@login_required
def batch_update_comments(request):
    """批量修改或删除评论 - 用于异常数据批量处理"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})
    try:
        import json
        data = json.loads(request.body.decode('utf-8')) if request.body else {}
        comment_ids = data.get('comment_ids', [])
        action = data.get('action')  # modify_time, modify_grade, delete
        new_value = data.get('new_value')

        if not comment_ids:
            return JsonResponse({'success': False, 'message': '请选择要处理的记录'})
        if len(comment_ids) > 500:
            return JsonResponse({'success': False, 'message': '单次最多处理500条'})

        valid_poi_ids = PSentiment.objects.values_list('poiId', flat=True).distinct()
        queryset = QusetAnswer.objects.filter(comment_id__in=comment_ids, poiId__in=valid_poi_ids)

        if action == 'delete':
            count = queryset.count()
            queryset.delete()
            OperationLog.objects.create(
                user=request.user,
                operation='批量删除异常评论',
                action='delete',
                target='评论数据',
                description=f'批量删除{count}条异常评论',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return JsonResponse({'success': True, 'message': f'已删除{count}条记录'})

        if action == 'modify_time':
            if not new_value:
                return JsonResponse({'success': False, 'message': '请填写新的时间'})
            try:
                from datetime import datetime
                dt = datetime.strptime(new_value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    dt = datetime.strptime(new_value, '%Y-%m-%d')
                except ValueError:
                    return JsonResponse({'success': False, 'message': '时间格式错误，请使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS'})
            count = queryset.update(release_time=timezone.make_aware(dt) if timezone.is_naive(dt) else dt)
            OperationLog.objects.create(
                user=request.user,
                operation='批量修改评论时间',
                action='update',
                target='评论数据',
                description=f'批量修改{count}条评论的发布时间为{new_value}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return JsonResponse({'success': True, 'message': f'已修改{count}条记录的时间'})

        if action == 'modify_grade':
            if new_value is None or new_value == '':
                return JsonResponse({'success': False, 'message': '请选择新的评分'})
            try:
                grade_num = float(new_value)
                if grade_num < 1 or grade_num > 5:
                    return JsonResponse({'success': False, 'message': '评分需在1-5之间'})
            except (TypeError, ValueError):
                return JsonResponse({'success': False, 'message': '评分格式错误'})
            count = queryset.update(comment_grade=grade_num)
            OperationLog.objects.create(
                user=request.user,
                operation='批量修改评论评分',
                action='update',
                target='评论数据',
                description=f'批量修改{count}条评论的评分为{grade_num}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            return JsonResponse({'success': True, 'message': f'已修改{count}条记录的评分'})

        return JsonResponse({'success': False, 'message': '未知操作类型'})
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': '请求数据格式错误'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})


@csrf_exempt
@login_required
def get_projects(request):
    """获取项目列表（AJAX） - 基于PSentiment表"""
    platform = request.GET.get('platform', '')
    
    if platform:
        projects = PSentiment.objects.filter(source_c=platform).values_list('title', flat=True).distinct().exclude(title__isnull=True).exclude(title='').order_by('title')
        projects_list = list(projects)
    else:
        projects_list = []
    
    return JsonResponse({
        'success': True,
        'projects': projects_list
    })


@csrf_exempt
@login_required
def get_statistics(request):
    """获取统计数据（ ajax）"""
    # 获取筛选参数
    platform = request.GET.get('platform', '')
    project = request.GET.get('project', '')
    
    start_date = request.GET.get('start_date', "")
    end_date = request.GET.get('end_date', '')
    
    rating = request.GET.get('rating', '')
    keyword = request.GET.get('keyword', '')
    
    # 构建查询 - 基于QusetAnswer表（与comments_list保持一致）
    # 如果没有选择平台或项目，返回空结果，避免统计过多数据
    if not platform and not project:
        queryset = QusetAnswer.objects.none()
    else:
        # 只查询在PSentiment表中有记录的poiId对应的评论
        valid_poi_ids = PSentiment.objects.values_list('poiId', flat=True).distinct()
        queryset = QusetAnswer.objects.filter(poiId__in=valid_poi_ids)
        
        # 添加日期筛选 - 使用extra()避免release_time__date的bug
        if start_date or end_date:
            where_conditions = []
            params = []
            
            if start_date:
                where_conditions.append('DATE(release_time) >= %s')
                params.append(start_date)
            
            if end_date:
                where_conditions.append('DATE(release_time) <= %s')
                params.append(end_date)
            
            if where_conditions:
                queryset = queryset.extra(where=where_conditions, params=params)
    
        # 通过PSentiment表进一步筛选评论
        sentiment_filter = PSentiment.objects.all()
        
        if platform:
            sentiment_filter = sentiment_filter.filter(source_c=platform)
        
        if project:
            sentiment_filter = sentiment_filter.filter(title__icontains=project)
        
        # 获取符合条件的poiId列表
        filtered_poi_ids = sentiment_filter.values_list('poiId', flat=True)
        filtered_poi_ids_list = list(filtered_poi_ids)
        
        if filtered_poi_ids_list:
            queryset = queryset.filter(poiId__in=filtered_poi_ids_list)
        else:
            queryset = queryset.none()  # 如果没有匹配的poiId，返回空查询集
    
    # 日期筛选 - 使用评论表的release_time
    # 评分筛选 - 使用评论表的comment_grade
    if rating:
        queryset = queryset.filter(comment_grade=rating)
    
    # 关键词搜索 - 使用评论表的字段
    if keyword:
        queryset = queryset.filter(
            Q(user_name__icontains=keyword) | 
            Q(comment_content__icontains=keyword)
        )
    
    # 统计数据 - 基于QusetAnswer表（平均评分使用comment_grade）
    total_comments = queryset.count()
    avg_rating = queryset.aggregate(avg=Avg('comment_grade'))['avg'] or 0
    total_likes = queryset.aggregate(total=Sum('like_num'))['total'] or 0
    total_replies = queryset.aggregate(total=Sum('reply_num'))['total'] or 0
    active_users = queryset.values('user_name').distinct().count()
    
    # 评分分布
    rating_distribution = queryset.values('comment_grade').annotate(
        count=Count('comment_id')
    ).order_by('comment_grade')
    
    # 活跃用户
    active_users_list = queryset.values('user_name').annotate(
        count=Count('comment_id')
    ).order_by('-count')[:10]
    
    return JsonResponse({
        'success': True,
        'statistics': {
            'total_comments': total_comments,
            'avg_rating': round(avg_rating, 2),
            'total_likes': total_likes,
            'total_replies': total_replies,
            'active_users': active_users,
        },
        'rating_distribution': list(rating_distribution),
        'active_users_list': list(active_users_list),
    })


@login_required
def export_data(request):
    """导出数据"""
    # 获取筛选参数
    platform = request.GET.get('platform', '')
    project = request.GET.get('project', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    rating = request.GET.get('rating', '')
    keyword = request.GET.get('keyword', '')
    export_format = request.GET.get('format', 'excel')
    
    # 构建查询
    queryset = QusetAnswer.objects.all()
    
    if platform:
        poi_ids = SpiderBase.objects.filter(SalesChannel=platform).values_list('poid', flat=True)
        queryset = queryset.filter(poiId__in=poi_ids)
    
    if project:
        poi_ids = SpiderBase.objects.filter(IteamName__icontains=project).values_list('poid', flat=True)
        queryset = queryset.filter(poiId__in=poi_ids)
    
    if start_date:
        queryset = queryset.filter(release_time__date__gte=start_date)
    
    if end_date:
        queryset = queryset.filter(release_time__date__lte=end_date)
    
    if rating:
        queryset = queryset.filter(comment_grade=rating)
    
    if keyword:
        queryset = queryset.filter(
            Q(user_name__icontains=keyword) | Q(comment_content__icontains=keyword)
        )
    
    queryset = queryset.order_by('-release_time')
    
    # 记录导出操作
    OperationLog.objects.create(
        user=request.user,
        operation='导出数据',
        action='export_data',
        target='评论数据',
        description=f'导出数据，筛选条件：平台={platform}, 项目={project}, 时间={start_date}~{end_date}, 评分={rating}, 关键词={keyword}',
        ip_address=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    if export_format == 'excel':
        return export_to_excel(queryset)
    else:
        return export_to_csv(queryset)


def export_to_excel(queryset):
    """导出为Excel格式"""
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet('评论数据')
    
    # 设置列标题
    headers = ['评论ID', '用户ID', '用户名', '项目ID', '项目名称', '平台来源', '评论等级', '评论内容', '点赞数', '回复数', '发布时间']
    for col, header in enumerate(headers):
        worksheet.write(0, col, header)
    
    # 写入数据
    for row, comment in enumerate(queryset, 1):
        worksheet.write(row, 0, comment.comment_id)
        worksheet.write(row, 1, comment.user_id)
        worksheet.write(row, 2, comment.user_name)
        worksheet.write(row, 3, comment.poiId)
        worksheet.write(row, 4, comment.poiName)
        worksheet.write(row, 5, comment.source_c)
        worksheet.write(row, 6, comment.comment_grade)
        worksheet.write(row, 7, comment.comment_content)
        worksheet.write(row, 8, comment.like_num)
        worksheet.write(row, 9, comment.reply_num)
        worksheet.write(row, 10, comment.release_time.strftime('%Y-%m-%d %H:%M:%S'))
    
    workbook.close()
    output.seek(0)
    
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=comments_data.xlsx'
    return response


def export_to_csv(queryset):
    """导出为CSV格式"""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename=comments_data.csv'
    
    writer = csv.writer(response)
    writer.writerow(['评论ID', '用户ID', '用户名', '项目ID', '项目名称', '平台来源', '评论等级', '评论内容', '点赞数', '回复数', '发布时间'])
    
    for comment in queryset:
        writer.writerow([
            comment.comment_id,
            comment.user_id,
            comment.user_name,
            comment.poiId,
            comment.poiName,
            comment.source_c,
            comment.comment_grade,
            comment.comment_content,
            comment.like_num,
            comment.reply_num,
            comment.release_time.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response


@login_required
@require_permission('sentiment_analysis_basic')
def sentiment_analysis(request):
    """情感分析统计页面"""
    # 获取筛选参数
    platform = request.GET.get('platform', '')
    project = request.GET.get('project', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    sentiment_type = request.GET.get('sentiment', '')
    
    # 构建查询条件 - 直接基于PSentiment表
    sentiment_query = PSentiment.objects.all()
    
    if platform:
        sentiment_query = sentiment_query.filter(source_c=platform)
    
    if project:
        sentiment_query = sentiment_query.filter(title=project)
    
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            sentiment_query = sentiment_query.filter(p_time__gte=start_datetime)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            sentiment_query = sentiment_query.filter(p_time__lt=end_datetime)
        except ValueError:
            pass
    
    # 基础统计 - 基于PSentiment表数据
    total_sentiments = sentiment_query.count()
    
    # 简化的情感分类（基于reply_num数量）
    positive_count = sentiment_query.filter(reply_num__gte=10).count()  # 回复数多表示关注度高，假设为正面
    negative_count = sentiment_query.filter(reply_num=0).count()  # 无回复假设为负面
    neutral_count = total_sentiments - positive_count - negative_count
    
    # 如果指定了情感类型，进一步筛选
    if sentiment_type == 'positive':
        sentiment_query = sentiment_query.filter(reply_num__gte=10)
    elif sentiment_type == 'negative':
        sentiment_query = sentiment_query.filter(reply_num=0)
    elif sentiment_type == 'neutral':
        sentiment_query = sentiment_query.filter(reply_num__gt=0, reply_num__lt=10)
    
    # 计算百分比
    positive_rate = (positive_count / total_sentiments * 100) if total_sentiments > 0 else 0
    negative_rate = (negative_count / total_sentiments * 100) if total_sentiments > 0 else 0
    neutral_rate = (neutral_count / total_sentiments * 100) if total_sentiments > 0 else 0
    
    # 平均置信度（基于回复数计算）
    avg_reply = sentiment_query.aggregate(avg_reply=Avg('reply_num'))['avg_reply'] or 0
    avg_confidence = 0.8 if avg_reply >= 10 or avg_reply == 0 else 0.6
    
    # 按平台统计 - 直接基于PSentiment表
    platform_stats = []
    platforms_in_sentiment = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='')
    
    for platform_name in platforms_in_sentiment:
        # 直接基于PSentiment表统计
        platform_data = sentiment_query.filter(source_c=platform_name)
        
        # 使用聚合查询提高性能
        stats = platform_data.aggregate(
            total=Count('poiId'),
            positive=Count('poiId', filter=Q(reply_num__gte=10)),
            negative=Count('poiId', filter=Q(reply_num=0)),
            avg_reply=Avg('reply_num')
        )
        
        total = stats['total']
        positive = stats['positive']
        negative = stats['negative']
        neutral = total - positive - negative
        
        if total > 0:
            platform_stats.append({
                'source_c': platform_name,
                'total': total,
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'avg_rating': stats['avg_reply'] or 0
            })
    
    platform_stats.sort(key=lambda x: x['total'], reverse=True)
    
    # 按项目统计 - 直接基于PSentiment表
    project_stats = []
    projects_in_sentiment = PSentiment.objects.values_list('title', flat=True).distinct().exclude(title__isnull=True).exclude(title='')[:10]  # 只显示前10个
    
    for project_name in projects_in_sentiment:
        # 直接基于PSentiment表统计
        project_data = sentiment_query.filter(title=project_name)
        
        # 使用聚合查询提高性能
        stats = project_data.aggregate(
            total=Count('poiId'),
            positive=Count('poiId', filter=Q(reply_num__gte=10)),
            negative=Count('poiId', filter=Q(reply_num=0)),
            avg_reply=Avg('reply_num')
        )
        
        total = stats['total']
        positive = stats['positive']
        negative = stats['negative']
        neutral = total - positive - negative
        
        if total > 0:
            project_stats.append({
                'poiName': project_name,
                'total': total,
                'positive': positive,
                'negative': negative,
                'neutral': neutral,
                'avg_rating': stats['avg_reply'] or 0
            })
    
    project_stats.sort(key=lambda x: x['total'], reverse=True)
    
    # 按时间统计（最近30天）- 基于PSentiment表
    end_date_for_chart = timezone.now()
    start_date_for_chart = end_date_for_chart - timedelta(days=30)
    
    time_stats = sentiment_query.filter(
        p_time__gte=start_date_for_chart
    ).extra(
        select={'date': 'DATE(p_time)'}
    ).values('date').annotate(
        total=Count('poiId'),
        positive=Count('poiId', filter=Q(reply_num__gte=10)),
        negative=Count('poiId', filter=Q(reply_num=0)),
        neutral=Count('poiId', filter=Q(reply_num__gt=0, reply_num__lt=10))
    ).order_by('date')[:30]  # 限制为30天
    
    # 获取平台和项目列表用于筛选 - 使用PSentiment表
    platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='').order_by('source_c')
    projects = PSentiment.objects.values_list('title', flat=True).distinct().exclude(title__isnull=True).exclude(title='').order_by('title')
    
    context = {
        'total_sentiments': total_sentiments,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'neutral_count': neutral_count,
        'positive_rate': round(positive_rate, 2),
        'negative_rate': round(negative_rate, 2),
        'neutral_rate': round(neutral_rate, 2),
        'avg_confidence': round(avg_confidence, 2),
        'platform_stats': platform_stats,
        'project_stats': project_stats,
        'time_stats': time_stats,
        'platforms': platforms,
        'projects': projects,
        'current_filters': {
            'platform': platform,
            'project': project,
            'start_date': start_date,
            'end_date': end_date,
            'sentiment': sentiment_type,
        }
    }
    
    return render(request, 'spiders/sentiment_analysis.html', context)


@csrf_exempt
@login_required
@require_permission('sentiment_analysis_basic')
def get_monthly_trend_data(request):
    """获取月度趋势数据（AJAX）"""
    try:
        # 获取筛选参数
        platform = request.GET.get('platform', '')
        project = request.GET.get('project', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        analysis_type = request.GET.get('analysis_type', 'monthly')
        
        # 构建基础查询
        sentiment_query = PSentiment.objects.all()
        
        if platform:
            sentiment_query = sentiment_query.filter(source_c=platform)
        
        if project:
            sentiment_query = sentiment_query.filter(title=project)
        
        if start_date:
            try:
                start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
                sentiment_query = sentiment_query.filter(p_time__gte=start_datetime)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
                sentiment_query = sentiment_query.filter(p_time__lt=end_datetime)
            except ValueError:
                pass
        
        # 获取月度数据
        monthly_data = []
        if analysis_type == 'monthly':
            # 获取过去12个月的数据
            current_date = timezone.now()
            for i in range(12, 0, -1):
                month_start = current_date.replace(day=1) - timedelta(days=30*i)
                month_end = month_start.replace(day=1) + timedelta(days=31)
                month_end = month_end.replace(day=1) - timedelta(days=1)
                
                month_data = sentiment_query.filter(
                    p_time__gte=month_start,
                    p_time__lt=month_end
                )
                
                positive = month_data.filter(reply_num__gte=10).count()
                negative = month_data.filter(reply_num=0).count()
                neutral = month_data.count() - positive - negative
                
                monthly_data.append({
                    'month': month_start.strftime('%Y-%m'),
                    'label': month_start.strftime('%m月'),
                    'positive': positive,
                    'negative': negative,
                    'neutral': neutral,
                    'total': month_data.count()
                })
        elif analysis_type == 'yearly':
            # 获取过去3年的数据
            current_year = timezone.now().year
            for year in range(current_year-2, current_year+1):
                year_start = datetime(year, 1, 1)
                year_end = datetime(year+1, 1, 1)
                
                year_data = sentiment_query.filter(
                    p_time__gte=year_start,
                    p_time__lt=year_end
                )
                
                positive = year_data.filter(reply_num__gte=10).count()
                negative = year_data.filter(reply_num=0).count()
                neutral = year_data.count() - positive - negative
                
                monthly_data.append({
                    'month': str(year),
                    'label': f'{year}年',
                    'positive': positive,
                    'negative': negative,
                    'neutral': neutral,
                    'total': year_data.count()
                })
        
        # 获取平台时间统计 - 更详细的月度年度分析
        platform_timeline_data = []
        platform_yearly_data = []
        
        platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='')
        current_time = timezone.now()
        
        for platform_name in platforms:
            platform_query = sentiment_query.filter(source_c=platform_name)
            
            # === 月度统计（过去12个月） ===
            monthly_stats = []
            monthly_labels = []
            
            for i in range(12, 0, -1):
                if analysis_type == 'monthly':
                    # 计算月的开始和结束
                    month_start = current_time.replace(day=1) - timedelta(days=30*i)
                    month_end = month_start.replace(day=1) + timedelta(days=31)
                    month_end = month_end.replace(day=1) - timedelta(days=1)
                    label = month_start.strftime('%m月')
                else:  # yearly
                    # 计算年的开始和结束
                    year_start = datetime(current_time.year - i + 1, 1, 1)
                    year_end = datetime(current_time.year - i + 2, 1, 1)
                    month_start = year_start
                    month_end = year_end
                    label = year_start.strftime('%Y年')
                
                month_data = platform_query.filter(
                    p_time__gte=month_start,
                    p_time__lt=month_end
                )
                
                positive_count = month_data.filter(reply_num__gte=10).count()
                negative_count = month_data.filter(reply_num=0).count()
                neutral_count = month_data.count() - positive_count - negative_count
                total_count = month_data.count()
                
                monthly_stats.append({
                    'period': label,
                    'total': total_count,
                    'positive': positive_count,
                    'negative': negative_count,
                    'neutral': neutral_count,
                    'start_date': month_start.strftime('%Y-%m-%d'),
                    'end_date': month_end.strftime('%Y-%m-%d')
                })
                monthly_labels.append(label)
            
            # === 年度统计（过去3年） ===
            yearly_stats = []
            for year_offset in range(2, -1, -1):  # 2023, 2024, 2025
                year_date = current_time.year - year_offset
                year_start = datetime(year_date, 1, 1)
                year_end = datetime(year_date + 1, 1, 1)
                
                year_data = platform_query.filter(
                    p_time__gte=year_start,
                    p_time__lt=year_end
                )
                
                yearly_stats.append({
                    'year': year_date,
                    'total': year_data.count(),
                    'positive': year_data.filter(reply_num__gte=10).count(),
                    'negative': year_data.filter(reply_num=0).count(),
                    'neutral': year_data.count() - year_data.filter(reply_num__gte=10).count() - year_data.filter(reply_num=0).count()
                })
            
            platform_timeline_data.append({
                'platform': platform_name,
                'monthly_statistics': monthly_stats,
                'yearly_statistics': yearly_stats,
                'summary': {
                    'total_all_time': platform_query.count(),
                    'current_year_total': platform_query.filter(p_time__year=current_time.year).count(),
                    'current_month_total': platform_query.filter(
                        p_time__year=current_time.year,
                        p_time__month=current_time.month
                    ).count()
                }
            })
        
        # 计算增长率
        latest_month_total = monthly_data[-1]['total'] if monthly_data else 0
        previous_month_total = monthly_data[-2]['total'] if len(monthly_data) >= 2 else 0
        monthly_growth = ((latest_month_total - previous_month_total) / previous_month_total * 100) if previous_month_total > 0 else 0
        
        yearly_data = []
        if len(monthly_data) >= 12:
            year_ago_total = monthly_data[0]['total'] if len(monthly_data) >= 12 else 0
            yearly_growth = ((latest_month_total - year_ago_total) / year_ago_total * 100) if year_ago_total > 0 else 0
            yearly_data = [yearly_growth]
        
        return JsonResponse({
            'success': True,
            'monthly_data': monthly_data,
            'platform_timeline_data': platform_timeline_data,
            'monthly_growth': round(monthly_growth, 2),
            'yearly_growth': round(yearly_data[0] if yearly_data else 12.5, 2) if yearly_data else 12.5,
            'platform_summary': {
                platform_data['platform']: platform_data['summary'] 
                for platform_data in platform_timeline_data
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_permission('sentiment_analysis_basic')
def get_platform_project_trends(request):
    """获取平台项目趋势分析数据（AJAX）"""
    try:
        from django.db.models import Count, Avg, Sum
        
        # 获取筛选参数
        analysis_type = request.GET.get('analysis_type', 'monthly')  # monthly/yearly
        platform_filter = request.GET.get('platform', '')  # 空字符串表示全部平台
        project_filter = request.GET.get('project', '')   # 空字符串表示全部项目
        
        # 基础查询
        base_query = PSentiment.objects.all()
        
        # 应用平台和项目过滤
        if platform_filter:
            base_query = base_query.filter(source_c=platform_filter)
        if project_filter:
            base_query = base_query.filter(title=project_filter)
        
        current_time = timezone.now()
        
        # === 平台级别统计 ===
        platforms_data = []
        all_platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='').order_by('source_c')
        
        for platform_name in all_platforms:
            platform_query = base_query.filter(source_c=platform_name) if not platform_filter else base_query
            if platform_filter and platform_name != platform_filter:
                continue  # 如果指定了平台，只处理该平台
                
            platform_stats = {
                'platform': platform_name,
                'total_count': platform_query.count(),
                'trend_data': [],
                'top_projects': []
            }
            
            # 时间趋势数据
            if analysis_type == 'monthly':
                # 过去12个月趋势
                for i in range(12, 0, -1):
                    month_start = current_time.replace(day=1) - timedelta(days=30*i)
                    month_end = month_start.replace(day=1) + timedelta(days=32)
                    
                    # 修复月份计算
                    if month_start.month == 12:
                        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
                    else:
                        month_end = month_start.replace(month=month_start.month + 1, day=1)
                    
                    month_data = platform_query.filter(
                        p_time__gte=month_start,
                        p_time__lt=month_end
                    )
                    
                    # 情感分析
                    positive = month_data.filter(reply_num__gte=10).count()
                    negative = month_data.filter(reply_num=0).count()
                    
                    platform_stats['trend_data'].append({
                        'period': month_start.strftime('%Y-%m'),
                        'label': month_start.strftime('%m月'),
                        'total': month_data.count(),
                        'positive': positive,
                        'negative': negative,
                        'neutral': month_data.count() - positive - negative
                    })
            else:
                # 年份趋势（只统计有数据的年份）
                for year in [2025, 2024, 2023]:  # 按优先级排序
                    year_data = platform_query.filter(p_time__year=year)
                    if year_data.count() > 0:  # 只包含有数据的年份
                        positive = year_data.filter(reply_num__gte=10).count()
                        negative = year_data.filter(reply_num=0).count()
                        
                        platform_stats['trend_data'].append({
                            'period': str(year),
                            'label': f'{year}年',
                            'total': year_data.count(),
                            'positive': positive,
                            'negative': negative,
                            'neutral': year_data.count() - positive - negative
                        })
            
            # 该项目下的热门项目
            top_projects = platform_query.values('title').annotate(
                project_count=Count('poiId'),
                avg_rating=Avg('reply_num'),
                total_replies=Sum('reply_num')
            ).order_by('-project_count')[:5]
            
            platform_stats['top_projects'] = list(top_projects)
            platforms_data.append(platform_stats)
        
        # === 项目级别统计 ===
        projects_data = []
        all_projects = base_query.values_list('title', flat=True).distinct().exclude(title__isnull=True).exclude(title='')[:10]
        
        for project_name in all_projects:
            project_query = base_query.filter(title=project_name)
            
            project_stats = {
                'project': project_name,
                'total_count': project_query.count(),
                'platforms_breakdown': [],
                'trend_data': []
            }
            
            # 各平台分布
            project_platforms = project_query.values('source_c').annotate(
                platform_count=Count('poiId')
            ).order_by('-platform_count')
            
            project_stats['platforms_breakdown'] = list(project_platforms)
            
            # 项目时间趋势
            if analysis_type == 'monthly':
                for i in range(12, 0, -1):
                    month_start = current_time.replace(day=1) - timedelta(days=30*i)
                    month_end = month_start.replace(day=1) + timedelta(days=32)
                    
                    if month_start.month == 12:
                        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
                    else:
                        month_end = month_start.replace(month=month_start.month + 1, day=1)
                    
                    month_data = project_query.filter(
                        p_time__gte=month_start,
                        p_time__lt=month_end
                    )
                    
                    project_stats['trend_data'].append({
                        'period': month_start.strftime('%Y-%m'),
                        'label': month_start.strftime('%m月'),
                        'count': month_data.count()
                    })
            else:
                for year in [2025, 2024, 2023]:  # 按优先级排序
                    year_data = project_query.filter(p_time__year=year)
                    if year_data.count() > 0:  # 只包含有数据的年份
                        project_stats['trend_data'].append({
                            'period': str(year),
                            'label': f'{year}年',
                            'count': year_data.count()
                        })
            
            projects_data.append(project_stats)
        
        # === 汇总统计 ===
        summary_stats = {
            'total_platforms': len(all_platforms),
            'total_projects': len(all_projects),
            'total_data': base_query.count(),
            'analysis_period': analysis_type,
            'filter_platform': platform_filter,
            'filter_project': project_filter,
            'platform_growth': [],
            'project_growth': []
        }
        
        # 平台增长趋势
        for platform_data in platforms_data:
            if len(platform_data['trend_data']) >= 2:
                current_period = platform_data['trend_data'][-1]['total']
                previous_period = platform_data['trend_data'][-2]['total']
                growth_rate = ((current_period - previous_period) / previous_period * 100) if previous_period > 0 else 0
                
                summary_stats['platform_growth'].append({
                    'platform': platform_data['platform'],
                    'growth_rate': round(growth_rate, 2),
                    'current_total': current_period
                })
        
        # 项目增长趋势
        for project_data in projects_data:
            if len(project_data['trend_data']) >= 2:
                current_period = project_data['trend_data'][-1]['count']
                previous_period = project_data['trend_data'][-2]['count']
                growth_rate = ((current_period - previous_period) / previous_period * 100) if previous_period > 0 else 0
                
                summary_stats['project_growth'].append({
                    'project': project_data['project'],
                    'growth_rate': round(growth_rate, 2),
                    'current_total': current_period
                })
        
        return JsonResponse({
            'success': True,
            'platforms_data': platforms_data,
            'projects_data': projects_data,
            'summary_stats': summary_stats,
            'analysis_type': analysis_type
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_permission('sentiment_analysis_basic')
def platform_statistics(request):
    """平台数据统计页面"""
    try:
        # 获取所有平台
        platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='').order_by('source_c')
        current_time = timezone.now()
        
        # 计算总数据量
        total_all_data = PSentiment.objects.count()
        
        # 构建详细统计
        platform_stats_detailed = []
        
        for platform_name in platforms:
            # 总数据统计
            total_data = PSentiment.objects.filter(source_c=platform_name)
            
            # 月度统计（过去12个月）
            monthly_data = []
            for i in range(12, 0, -1):
                month_start = current_time.replace(day=1) - timedelta(days=30*i)
                month_target = month_start
                
                month_end = month_target.replace(day=1) + timedelta(days=32) if month_target.month == 12 else month_target.replace(month=month_target.month + 1, day=1)
                month_end = month_end.replace(day=1) - timedelta(days=1)
                
                month_data = total_data.filter(
                    p_time__gte=month_start,
                    p_time__lt=month_end
                )
                
                monthly_data.append({
                    'month': month_start.strftime('%Y-%m'),
                    'label': month_start.strftime('%Y年%m月'),
                    'count': month_data.count()
                })
            
            # 年度统计（基于实际数据年份）
            yearly_data = []
            # 由于数据主要分布在2025年，我们统计有数据的年份
            for year_date in [2025, 2024, 2023]:  # 按重要性排序
                year_count = total_data.filter(p_time__year=year_date).count()
                if year_count > 0:  # 只包含有数据的年份
                    yearly_data.append({
                        'year': year_date,
                        'count': year_count
                    })
            
            # 当年月度分解
            current_year_monthly = []
            for month in range(1, 13):
                month_count = total_data.filter(
                    p_time__year=current_time.year,
                    p_time__month=month
                ).count()
                
                if month_count > 0:  # 只显示有数据的月份
                    current_year_monthly.append({
                        'month': month,
                        'label': f'{month}月',
                        'count': month_count
                    })
            
            platform_stats_detailed.append({
                'platform': platform_name,
                'total_count': total_data.count(),
                'monthly_data': monthly_data,
                'yearly_data': yearly_data,
                'current_year_monthly': current_year_monthly
            })
        
        context = {
            'platforms': platforms,
            'platform_stats_detailed': platform_stats_detailed,
            'current_year': current_time.year,
            'current_month': current_time.month,
            'total_all_data': total_all_data
        }
        
        return render(request, 'spiders/platform_statistics.html', context)
        
    except Exception as e:
        context = {'error': str(e)}
        return render(request, 'spiders/platform_statistics.html', context)


@csrf_exempt
@login_required
@require_permission('sentiment_analysis_advanced')
def get_sentiment_analytics(request):
    """获取多维度情感分析数据（AJAX）"""
    try:
        # 获取筛选参数
        platform = request.GET.get('platform', '')
        project = request.GET.get('project', '')
        start_date = request.GET.get('start_date', '')
        end_date = request.GET.get('end_date', '')
        
        # ===== 1. 时间趋势分析 =====
        from django.db.models import Count
        from datetime import datetime, timedelta
        
        # 月度数据增长趋势
        monthly_data = []
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        for i in range(12):
            month_start = datetime(2025, i+1, 1)
            month_end = month_start + timedelta(days=32) - timedelta(days=month_start.day)
            
            month_query = PSentiment.objects.all()
            if platform:
                month_query = month_query.filter(source_c=platform)
            if start_date:
                month_query = month_query.filter(p_time__gte=start_date)
            if end_date:
                month_query = month_query.filter(p_time__lte=end_date)
                
            if i < 12:
                month_query = month_query.filter(
                    p_time__month=i+1,
                    p_time__year=2025
                )
            
            month_count = month_query.count()
            monthly_data.append(month_count)
        
        # ===== 2. 平台深度分析 =====
        platforms_for_radar = []
        platform_details = []
        
        for platform_name in PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='')[:6]:
            platform_data = PSentiment.objects.filter(source_c=platform_name)
            
            # 计算多维指标
            total_count = platform_data.count()
            
            # 用户活跃度 (基于评论参与度)
            active_users = platform_data.filter(y_name__isnull=False).exclude(y_name='').values('y_name').distinct().count()
            user_activity_score = min(100, active_users * 5)
            
            # 内容质量 (基于回复数和评论数量)
            avg_reply = platform_data.aggregate(avg=Avg('reply_num'))['avg'] or 0
            avg_comment = platform_data.aggregate(avg=Avg('comment_num'))['avg'] or 0
            content_quality_score = min(100, (avg_reply + avg_comment) * 10)
            
            # 互动性强
            high_interaction = platform_data.filter(reply_num__gte=5).count()
            interaction_score = min(100, (high_interaction / total_count * 100) if total_count > 0 else 0)
            
            # 话题热度 (基于回复率)
            total_replies = platform_data.aggregate(total=Sum('reply_num'))['total'] or 0
            topic_heat_score = min(100, total_replies / total_count) if total_count > 0 else 0
            
            # 情感正向度
            positive_count = platform_data.filter(reply_num__gte=5).count()
            sentiment_score = min(100, (positive_count / total_count * 100) if total_count > 0 else 50)
            
            platforms_for_radar.append(platform_name)
            platform_details.append({
                'labels': ['用户活跃度', '内容质量', '互动性强', '话题热度', '情感正向度'],
                'data': [user_activity_score, content_quality_score, interaction_score, topic_heat_score, sentiment_score]
            })
        
        # ===== 3. 用户行为分析 =====
        
        # 用户参与度分布（基于评论活跃度）
        # 轻度参与：评论数少，回复数少
        light_users = QusetAnswer.objects.filter(
            poiId__in=PSentiment.objects.values_list('poiId', flat=True),
            like_num__lte=5,
            reply_num__lte=2
        ).count()
        
        # 中度参与：评论数中等
        medium_users = QusetAnswer.objects.filter(
            poiId__in=PSentiment.objects.values_list('poiId', flat=True),
            like_num__gt=5,
            like_num__lte=15,
            reply_num__gt=2,
            reply_num__lte=10
        ).count()
        
        # 重度参与：评论数多
        heavy_users = QusetAnswer.objects.filter(
            poiId__in=PSentiment.objects.values_list('poiId', flat=True),
            like_num__gt=15,
            reply_num__gt=10
        ).count()
        
        # 评论质量评估
        high_quality = QusetAnswer.objects.filter(
            poiId__in=PSentiment.objects.values_list('poiId', flat=True),
            comment_content__length__gt=50,
            like_num__gte=5
        ).count()
        
        medium_quality = QusetAnswer.objects.filter(
            poiId__in=PSentiment.objects.values_list('poiId', flat=True),
            comment_content__length__gt=20,
            comment_content__length__lte=50
        ).count()
        
        low_quality = QusetAnswer.objects.filter(
            poiId__in=PSentiment.objects.values_list('poiId', flat=True),
            comment_content__length__lte=20
        ).count()
        
        # 话题热度排名
        topic_heat = []
        top_projects = PSentiment.objects.values('title').annotate(
            total_count=Count('poiId'),
            total_replies=Sum('reply_num')
        ).exclude(title__isnull=True).exclude(title='').order_by('-total_replies')[:4]
        
        for project in top_projects:
            topic_heat.append({
                'name': project['title'],
                'count': project['total_replies'] or 0
            })
        
        # ===== 4. 商业价值分析 =====
        
        # 项目商业敏感度矩阵 (商业价值 vs 情感风险)
        business_analysis = []
        projects_for_business = PSentiment.objects.values('title').annotate(
            total_count=Count('poiId'),
            avg_reply=Avg('reply_num'),
            total_replies=Sum('reply_num')
        ).exclude(title__isnull=True).exclude(title='').order_by('-total_count')[:6]
        
        for project in projects_for_business:
            project_title = project['title']
            comment_count = QusetAnswer.objects.filter(
                poiId__in=PSentiment.objects.filter(title=project_title).values_list('poiId', flat=True)
            ).count()
            
            # 商业价值：基于关注度和参与度
            business_value = min(100, (project['total_count'] + comment_count) * 2)
            
            # 情感风险：基于负面情感比例
            sentiment_query = PSentiment.objects.filter(title=project_title)
            negative_rate = sentiment_query.filter(reply_num=0).count() / sentiment_query.count() * 100 if sentiment_query.count() > 0 else 0
            sentiment_risk = min(100, negative_rate)
            
            business_analysis.append({
                'name': project_title,
                'business_value': business_value,
                'sentiment_risk': sentiment_risk
            })
        
        # 消费者洞察矩阵 (用户满意度 vs 推荐意愿)
        consumer_insights = []
        for project in projects_for_business:
            project_title = project['title']
            
            # 用户满意度：基于平均评分和点赞数
            satisfaction_data = QusetAnswer.objects.filter(
                poiId__in=PSentiment.objects.filter(title=project_title).values_list('poiId', flat=True)
            )
            
            avg_satisfaction = satisfaction_data.aggregate(
                avg=Avg('comment_grade')
            )['avg'] or 3
            
            satisfaction_score = min(100, avg_satisfaction * 20)
            
            # 推荐意愿：基于积极回复和互动
            recommendation_score = min(100, (project['avg_reply'] or 0) * 10)
            
            consumer_insights.append({
                'name': project_title,
                'satisfaction': satisfaction_score,
                'recommendation': recommendation_score,
                'bubble_size': project['total_count']
            })
        
        return JsonResponse({
            'success': True,
            'monthly_growth': monthly_data,
            'platform_radar': {
                'platforms': platforms_for_radar,
                'data': platform_details
            },
            'user_behavior': {
                'engagement': [light_users, medium_users, heavy_users],
                'quality': [high_quality, medium_quality, low_quality]
            },
            'topic_heat': topic_heat,
            'business_analysis': business_analysis,
            'consumer_insights': consumer_insights
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'分析失败: {str(e)}'
        })


@login_required
def get_sentiment_statistics(request):
    """获取情感分析统计数据（AJAX）"""
    # 获取筛选参数
    platform = request.GET.get('platform', '')
    project = request.GET.get('project', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    sentiment_type = request.GET.get('sentiment', '')
    
    # 构建查询条件 - 通过poiId关联SpiderBase表
    comment_query = QusetAnswer.objects.all()
    
    if platform:
        # 通过poiId关联查询平台
        platform_poi_ids = SpiderBase.objects.filter(SalesChannel=platform).values_list('poid', flat=True)
        comment_query = comment_query.filter(poiId__in=platform_poi_ids)
    
    if project:
        # 通过poiId关联查询项目
        project_poi_ids = SpiderBase.objects.filter(IteamName=project).values_list('poid', flat=True)
        comment_query = comment_query.filter(poiId__in=project_poi_ids)
    
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, '%Y-%m-%d')
            comment_query = comment_query.filter(release_time__gte=start_datetime)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_datetime = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            comment_query = comment_query.filter(release_time__lt=end_datetime)
        except ValueError:
            pass
    
    if sentiment_type == 'positive':
        comment_query = comment_query.filter(comment_grade__gte=4)
    elif sentiment_type == 'negative':
        comment_query = comment_query.filter(comment_grade__lte=2)
    elif sentiment_type == 'neutral':
        comment_query = comment_query.filter(comment_grade__gt=2, comment_grade__lt=4)
    
    # 基础统计
    total_comments = comment_query.count()
    positive_count = comment_query.filter(comment_grade__gte=4).count()
    negative_count = comment_query.filter(comment_grade__lte=2).count()
    neutral_count = comment_query.filter(comment_grade__gt=2, comment_grade__lt=4).count()
    
    # 计算百分比
    positive_rate = (positive_count / total_comments * 100) if total_comments > 0 else 0
    negative_rate = (negative_count / total_comments * 100) if total_comments > 0 else 0
    neutral_rate = (neutral_count / total_comments * 100) if total_comments > 0 else 0
    
    # 平均置信度（基于评分计算）
    avg_rating = comment_query.aggregate(avg_rating=Avg('comment_grade'))['avg_rating'] or 0
    avg_confidence = 0.8 if avg_rating >= 4 or avg_rating <= 2 else 0.6
    
    statistics = {
        'total_sentiments': total_comments,
        'positive_count': positive_count,
        'negative_count': negative_count,
        'neutral_count': neutral_count,
        'positive_rate': round(positive_rate, 2),
        'negative_rate': round(negative_rate, 2),
        'neutral_rate': round(neutral_rate, 2),
        'avg_confidence': round(avg_confidence, 2),
    }
    
    return JsonResponse({'success': True, 'statistics': statistics})


# ==================== 数据管理模块 ====================

@login_required
def data_management(request):
    """数据管理主页面 - 基于spider_base表"""
    # 获取筛选参数
    platform = request.GET.get('platform', '')
    status = request.GET.get('status', '')
    search_keyword = request.GET.get('search', '')
    page = int(request.GET.get('page', 1))
    per_page = 20
    
    # 构建查询条件 - 基于spider_base表
    spider_query = SpiderBase.objects.select_related('created_by').all()
    
    if platform:
        spider_query = spider_query.filter(SalesChannel=platform)
    
    if status:
        spider_query = spider_query.filter(IteamState=status)
    
    if search_keyword:
        spider_query = spider_query.filter(
            Q(IteamName__icontains=search_keyword) |
            Q(request_data__icontains=search_keyword) |
            Q(SalesChannel__icontains=search_keyword)
        )
    
    # 分页
    total_count = spider_query.count()
    start = (page - 1) * per_page
    end = start + per_page
    spiders = spider_query.order_by('-id')[start:end]
    
    # 获取平台和状态列表
    platforms = SpiderBase.objects.values_list('SalesChannel', flat=True).distinct().exclude(SalesChannel__isnull=True).exclude(SalesChannel='').order_by('SalesChannel')
    statuses = SpiderBase.objects.values_list('IteamState', flat=True).distinct().exclude(IteamState__isnull=True).exclude(IteamState='').order_by('IteamState')
    
    # 计算总页数
    total_pages = (total_count + per_page - 1) // per_page
    
    # 生成页码范围
    start_page = max(1, page - 5)
    end_page = min(total_pages, page + 5)
    page_range = range(start_page, end_page + 1)
    
    context = {
        'spiders': spiders,
        'platforms': platforms,
        'statuses': statuses,
        'current_filters': {
            'platform': platform,
            'status': status,
            'search': search_keyword,
        },
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'total_count': total_count,
            'per_page': per_page,
            'has_previous': page > 1,
            'has_next': page < total_pages,
            'previous_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None,
            'page_range': page_range,
        }
    }
    
    return render(request, 'spiders/data_management.html', context)


def _spider_config_duplicate_exists(title, platform, exclude_id=None):
    """同一平台下项目名称不可重复；不同平台允许同名项目。"""
    qs = SpiderBase.objects.filter(IteamName=title, SalesChannel=platform)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    return qs.exists()


def _parse_optional_int(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@login_required
@csrf_exempt
def add_spider(request):
    """添加爬虫数据"""
    if request.method == 'POST':
        try:
            # 获取表单数据
            title = (request.POST.get('IteamName') or request.POST.get('title') or '').strip()
            platform = (request.POST.get('SalesChannel') or request.POST.get('platform') or '').strip()
            industry = request.POST.get('industry')
            request_data = request.POST.get('request_data')
            project_id = request.POST.get('project_id')
            status = (request.POST.get('IteamState') or request.POST.get('status') or '').strip()
            poid = _parse_optional_int(request.POST.get('poid'))
            sort_type = request.POST.get('sort_type')
            total_collection_page = _parse_optional_int(request.POST.get('total_collection_page'))
            city = (request.POST.get('city') or '').strip() or None
            
            # 验证必填字段
            if not all([title, platform]):
                return JsonResponse({'success': False, 'message': '请填写所有必填字段'})
            
            if not status:
                status = 'active'
            else:
                status = SpiderBase.normalize_state(status)
            
            # 同一平台下项目名称不可重复（不同平台可同名，如各平台的「深圳世界之窗」）
            if _spider_config_duplicate_exists(title, platform):
                return JsonResponse({
                    'success': False,
                    'message': f'平台「{platform}」下已存在项目「{title}」，请勿重复添加',
                })
            
            # 创建爬虫数据
            spider = SpiderBase.objects.create(
                IteamName=title,
                SalesChannel=platform,
                industry=industry,
                request_data=request_data or '',
                project_id=project_id,
                IteamState=status,
                poid=poid,
                sort_type=sort_type,
                total_collection_page=total_collection_page,
                city=city,
                created_by=request.user if request.user.is_authenticated else None,
            )
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='添加爬虫数据',
                action='create',
                target=f'SpiderBase-{spider.id}',
                description=f'添加爬虫: {title} ({platform})',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True, 
                'message': '添加成功',
                'spider_id': spider.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'添加失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@login_required
@csrf_exempt
def edit_spider(request, spider_id):
    """编辑爬虫数据"""
    if request.method == 'POST':
        try:
            spider = SpiderBase.objects.get(id=spider_id)
            
            # 获取表单数据
            title = (request.POST.get('IteamName') or request.POST.get('title') or '').strip()
            platform = (request.POST.get('SalesChannel') or request.POST.get('platform') or '').strip()
            industry = request.POST.get('industry')
            request_data = request.POST.get('request_data')
            project_id = request.POST.get('project_id')
            status = (request.POST.get('IteamState') or request.POST.get('status') or '').strip()
            poid = _parse_optional_int(request.POST.get('poid'))
            sort_type = request.POST.get('sort_type')
            total_collection_page = _parse_optional_int(request.POST.get('total_collection_page'))
            city = (request.POST.get('city') or '').strip() or None
            
            # 验证必填字段
            if not all([title, platform]):
                return JsonResponse({'success': False, 'message': '请填写所有必填字段'})
            
            if status:
                status = SpiderBase.normalize_state(status)
            else:
                status = spider.IteamState or 'active'
            
            if _spider_config_duplicate_exists(title, platform, exclude_id=spider_id):
                return JsonResponse({
                    'success': False,
                    'message': f'平台「{platform}」下已存在项目「{title}」，请更换名称或平台',
                })
            
            # 更新数据
            old_data = f'{spider.IteamName} ({spider.SalesChannel})'
            
            spider.IteamName = title
            spider.SalesChannel = platform
            spider.industry = industry
            spider.request_data = request_data or ''
            spider.project_id = project_id
            spider.IteamState = status
            spider.poid = poid
            spider.sort_type = sort_type
            spider.total_collection_page = total_collection_page
            spider.city = city
            spider.save()
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='编辑爬虫数据',
                action='update',
                target=f'SpiderBase-{spider.id}',
                description=f'编辑爬虫: {old_data} -> {title} ({platform})',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True, 
                'message': '编辑成功'
            })
            
        except SpiderBase.DoesNotExist:
            return JsonResponse({'success': False, 'message': '记录不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'编辑失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@login_required
@csrf_exempt
def delete_spider(request, spider_id):
    """删除爬虫数据"""
    if request.method == 'POST':
        try:
            spider = SpiderBase.objects.get(id=spider_id)
            spider_data = f'{spider.IteamName} ({spider.SalesChannel})'
            
            # 删除数据
            spider.delete()
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='删除爬虫数据',
                action='delete',
                target=f'SpiderBase-{spider_id}',
                description=f'删除爬虫: {spider_data}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True, 
                'message': '删除成功'
            })
            
        except SpiderBase.DoesNotExist:
            return JsonResponse({'success': False, 'message': '记录不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'删除失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@login_required
@csrf_exempt
def toggle_spider_status(request, spider_id):
    """切换配置激活/关闭状态"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '请求方法错误'})
    try:
        spider = SpiderBase.objects.get(id=spider_id)
        old_label = spider.state_label
        new_state = spider.toggle_config_state()
        new_label = spider.state_label
        OperationLog.objects.create(
            user=request.user,
            operation='切换爬虫状态',
            action='update',
            target=f'SpiderBase-{spider.id}',
            description=f'状态切换: {spider.IteamName} ({spider.SalesChannel}) {old_label} -> {new_label}',
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        return JsonResponse({
            'success': True,
            'message': f'已切换为「{new_label}」',
            'IteamState': new_state,
            'state_label': new_label,
            'is_active': spider.is_config_active,
        })
    except SpiderBase.DoesNotExist:
        return JsonResponse({'success': False, 'message': '记录不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'切换失败: {str(e)}'})


@login_required
def get_spider_detail(request, spider_id):
    """获取爬虫详情"""
    try:
        spider = SpiderBase.objects.get(id=spider_id)
        return JsonResponse({
            'success': True,
            'spider': {
                'id': spider.id,
                'IteamName': spider.IteamName,
                'SalesChannel': spider.SalesChannel,
                'industry': spider.industry,
                'request_data': spider.request_data,
                'project_id': spider.project_id,
                'IteamState': spider.IteamState,
                'normalized_state': spider.normalized_state,
                'state_label': spider.state_label,
                'is_active': spider.is_config_active,
                'poid': spider.poid,
                'sort_type': spider.sort_type,
                'total_collection_page': spider.total_collection_page,
                'city': spider.city,
                'created_at': spider.created_at.strftime('%Y-%m-%d %H:%M') if spider.created_at else '',
                'updated_at': spider.updated_at.strftime('%Y-%m-%d %H:%M') if spider.updated_at else '',
                'created_by': spider.created_by.username if spider.created_by else '',
            }
        })
    except SpiderBase.DoesNotExist:
        return JsonResponse({'success': False, 'message': '记录不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'获取详情失败: {str(e)}'})


# ==================== 用户管理模块 ====================

@login_required
@csrf_exempt
def user_management(request):
    """用户管理主页面"""
    # 获取筛选参数（支持GET和POST）
    if request.method == 'POST':
        search_keyword = request.POST.get('search', '')
        platform_filter = request.POST.get('platform', '')
        project_filter = request.POST.get('project', '')
    else:
        search_keyword = request.GET.get('search', '')
        platform_filter = request.GET.get('platform', '')
        project_filter = request.GET.get('project', '')
    
    page = int(request.GET.get('page', 1))
    per_page = 20
    
    # 获取所有平台和项目数据
    platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().order_by('source_c')
    platforms = [p for p in platforms if p]  # 过滤掉空值
    
    # 根据平台筛选项目
    if platform_filter:
        projects = PSentiment.objects.filter(
            source_c=platform_filter
        ).values('title').distinct().order_by('title')
    else:
        projects = PSentiment.objects.values('title').distinct().order_by('title')
    
    # 构建查询条件
    user_query = User.objects.all()
    
    if search_keyword:
        user_query = user_query.filter(
            Q(username__icontains=search_keyword) |
            Q(email__icontains=search_keyword) |
            Q(first_name__icontains=search_keyword) |
            Q(last_name__icontains=search_keyword)
        )
    
    # 分页
    total_count = user_query.count()
    start = (page - 1) * per_page
    end = start + per_page
    users = user_query.order_by('-date_joined')[start:end]
    
    # 计算总页数
    total_pages = (total_count + per_page - 1) // per_page
    
    # 生成页码范围
    start_page = max(1, page - 5)
    end_page = min(total_pages, page + 5)
    page_range = range(start_page, end_page + 1)
    
    context = {
        'users': users,
        'platforms': platforms,
        'projects': projects,
        'current_filters': {
            'search': search_keyword,
            'platform': platform_filter,
            'project': project_filter,
        },
        'pagination': {
            'current_page': page,
            'total_pages': total_pages,
            'total_count': total_count,
            'per_page': per_page,
            'has_previous': page > 1,
            'has_next': page < total_pages,
            'previous_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None,
            'page_range': page_range,
        }
    }
    
    # 如果是AJAX请求，只返回表格部分
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'spiders/user_management_content.html', context)
    
    return render(request, 'spiders/user_management.html', context)


@csrf_exempt
def add_user(request):
    """添加用户"""
    # 检查用户是否登录（手动检查，避免重定向）
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': '未登录，请先登录'}, status=401)
    
    if request.method == 'POST':
        try:
            # 获取表单数据
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            is_staff = request.POST.get('is_staff') in ['on', 'true', True, 'True']
            is_active = request.POST.get('is_active') in ['on', 'true', True, 'True']
            
            # 验证必填字段
            if not all([username, email, password]):
                return JsonResponse({'success': False, 'message': '请填写所有必填字段'})
            
            # 检查用户名是否已存在
            if User.objects.filter(username=username).exists():
                return JsonResponse({'success': False, 'message': '用户名已存在'})
            
            # 检查邮箱是否已存在
            if User.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'message': '邮箱已存在'})
            
            # 创建用户
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_staff=is_staff,
                is_active=is_active
            )
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='添加用户',
                action='create',
                target=f'User-{user.id}',
                description=f'添加用户: {username}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True, 
                'message': '添加成功',
                'user_id': user.id
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'添加失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@csrf_exempt
def edit_user(request, user_id):
    """编辑用户"""
    # 检查用户是否登录（手动检查，避免重定向）
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': '未登录，请先登录'}, status=401)
    
    if request.method == 'POST':
        try:
            user = User.objects.get(id=user_id)
            
            # 获取表单数据
            username = request.POST.get('username')
            email = request.POST.get('email')
            password = request.POST.get('password')
            first_name = request.POST.get('first_name', '')
            last_name = request.POST.get('last_name', '')
            is_staff = request.POST.get('is_staff') in ['on', 'true', True, 'True']
            is_active = request.POST.get('is_active') in ['on', 'true', True, 'True']
            
            # 验证必填字段
            if not all([username, email]):
                return JsonResponse({'success': False, 'message': '请填写所有必填字段'})
            
            # 检查用户名是否已被其他用户使用
            if User.objects.filter(username=username).exclude(id=user_id).exists():
                return JsonResponse({'success': False, 'message': '用户名已被其他用户使用'})
            
            # 检查邮箱是否已被其他用户使用
            if User.objects.filter(email=email).exclude(id=user_id).exists():
                return JsonResponse({'success': False, 'message': '邮箱已被其他用户使用'})
            
            # 更新用户信息
            old_username = user.username
            user.username = username
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.is_staff = is_staff
            user.is_active = is_active
            
            # 如果提供了新密码，则更新密码
            if password:
                user.set_password(password)
            
            user.save()
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='编辑用户',
                action='update',
                target=f'User-{user.id}',
                description=f'编辑用户: {old_username} -> {username}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True, 
                'message': '编辑成功'
            })
            
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': '用户不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'编辑失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@csrf_exempt
def delete_user(request, user_id):
    """删除用户"""
    # 检查用户是否登录（手动检查，避免重定向）
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': '未登录，请先登录'}, status=401)
    
    if request.method == 'POST':
        try:
            user = User.objects.get(id=user_id)
            username = user.username
            
            # 不能删除自己
            if user.id == request.user.id:
                return JsonResponse({'success': False, 'message': '不能删除自己的账户'})
            
            # 删除用户
            user.delete()
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='删除用户',
                action='delete',
                target=f'User-{user_id}',
                description=f'删除用户: {username}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True, 
                'message': '删除成功'
            })
            
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': '用户不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'删除失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


def get_user_detail(request, user_id):
    """获取用户详情"""
    # 检查用户是否登录（手动检查，避免重定向）
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': '未登录，请先登录'}, status=401)
    
    try:
        user = User.objects.get(id=user_id)
        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_staff': user.is_staff,
                'is_active': user.is_active,
                'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else ''
            }
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': '用户不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'获取详情失败: {str(e)}'})


@login_required
def user_project_permissions(request, user_id):
    """用户项目权限管理页面"""
    try:
        user = User.objects.get(id=user_id)
        
        # 获取用户的项目权限
        permissions = UserProjectPermission.objects.filter(user=user).order_by('-granted_at')
        
        # 获取所有平台
        platforms = PSentiment.objects.values_list('source_c', flat=True).distinct().order_by('source_c')
        platforms = [p for p in platforms if p]  # 过滤掉空值
        
        context = {
            'user': user,
            'permissions': permissions,
            'platforms': platforms
        }
        
        return render(request, 'spiders/user_project_permissions.html', context)
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'message': '用户不存在'})


@login_required
@csrf_exempt
def assign_project_permission(request):
    """分配项目权限"""
    if request.method == 'POST':
        try:
            user_id = request.POST.get('user_id')
            project_poi_id = request.POST.get('project_poi_id')
            notes = request.POST.get('notes', '')
            
            # 验证必填字段
            if not all([user_id, project_poi_id]):
                return JsonResponse({'success': False, 'message': '请填写所有必填字段'})
            
            # 获取用户和项目信息
            user = User.objects.get(id=user_id)
            project = PSentiment.objects.get(poiId=project_poi_id)
            
            # 检查权限是否已存在
            if UserProjectPermission.objects.filter(user=user, project_poi_id=project_poi_id).exists():
                return JsonResponse({'success': False, 'message': '该用户已拥有此项目权限'})
            
            # 创建项目权限
            permission = UserProjectPermission.objects.create(
                user=user,
                project_poi_id=project_poi_id,
                project_name=project.title,
                platform=project.source_c,
                granted_by=request.user,
                notes=notes
            )
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='分配项目权限',
                action='create',
                target=f'UserProjectPermission-{permission.id}',
                description=f'为用户 {user.username} 分配项目权限: {project.title}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True, 
                'message': '权限分配成功',
                'permission_id': permission.id
            })
            
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'message': '用户不存在'})
        except PSentiment.DoesNotExist:
            return JsonResponse({'success': False, 'message': '项目不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'分配失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@login_required
@csrf_exempt
def revoke_project_permission(request, permission_id):
    """撤销项目权限"""
    if request.method == 'POST':
        try:
            permission = UserProjectPermission.objects.get(id=permission_id)
            user = permission.user
            project_name = permission.project_name
            
            # 删除权限
            permission.delete()
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='撤销项目权限',
                action='delete',
                target=f'UserProjectPermission-{permission_id}',
                description=f'撤销用户 {user.username} 的项目权限: {project_name}',
                ip_address=request.META.get('REMOTE_ADDR', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            return JsonResponse({
                'success': True, 
                'message': '权限撤销成功'
            })
            
        except UserProjectPermission.DoesNotExist:
            return JsonResponse({'success': False, 'message': '权限不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'撤销失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@login_required
def get_platform_projects(request):
    """获取指定平台下的项目列表"""
    platform = request.GET.get('platform')
    
    if not platform:
        return JsonResponse({'success': False, 'message': '请指定平台'})
    
    try:
        # 获取该平台下的所有项目
        projects = PSentiment.objects.filter(
            source_c=platform
        ).values('poiId', 'title').distinct().order_by('title')
        
        # 过滤掉无效数据
        valid_projects = []
        for project in projects:
            if project['poiId'] and project['title']:
                valid_projects.append(project)
        
        return JsonResponse({
            'success': True,
            'projects': valid_projects
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'获取项目失败: {str(e)}'})


# ==================== 手机APP API接口 ====================

@csrf_exempt
def mobile_api_login(request):
    """手机APP登录接口"""
    if request.method == 'POST':
        try:
            import json
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')
            device_info = data.get('device_info', '')
            
            # 验证用户
            user = authenticate(username=username, password=password)
            if user and user.is_active:
                # 生成API令牌
                token = secrets.token_urlsafe(32)
                expires_at = timezone.now() + timedelta(days=30)  # 30天过期
                
                # 创建或更新令牌
                api_token, created = MobileAPIToken.objects.get_or_create(
                    user=user,
                    defaults={
                        'token': token,
                        'expires_at': expires_at,
                        'device_info': device_info
                    }
                )
                
                if not created:
                    # 更新现有令牌
                    api_token.token = token
                    api_token.expires_at = expires_at
                    api_token.device_info = device_info
                    api_token.is_active = True
                    api_token.save()
                
                return JsonResponse({
                    'success': True,
                    'message': '登录成功',
                    'token': token,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name
                    }
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': '用户名或密码错误'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'登录失败: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


def verify_api_token(token):
    """验证API令牌"""
    try:
        api_token = MobileAPIToken.objects.get(token=token, is_active=True)
        
        if api_token.is_expired():
            api_token.is_active = False
            api_token.save()
            return None
        
        # 更新最后使用时间
        api_token.last_used = timezone.now()
        api_token.save()
        
        return api_token.user
    except MobileAPIToken.DoesNotExist:
        return None


@csrf_exempt
def mobile_api_user_projects(request):
    """手机APP获取用户项目接口"""
    if request.method == 'GET':
        try:
            # 验证API令牌
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            user = verify_api_token(token)
            
            if not user:
                return JsonResponse({
                    'success': False,
                    'message': '无效的API令牌'
                })
            
            # 获取用户的项目权限
            permissions = UserProjectPermission.objects.filter(user=user, is_active=True)
            
            projects = []
            for permission in permissions:
                # 获取项目的最新数据统计
                try:
                    project = PSentiment.objects.get(poiId=permission.project_poi_id)
                    comment_count = QusetAnswer.objects.filter(poiId=permission.project_poi_id).count()
                    
                    projects.append({
                        'poi_id': permission.project_poi_id,
                        'name': permission.project_name,
                        'platform': permission.platform,
                        'comment_count': comment_count,
                        'granted_at': permission.granted_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'notes': permission.notes or ''
                    })
                except PSentiment.DoesNotExist:
                    continue
            
            return JsonResponse({
                'success': True,
                'message': '获取成功',
                'projects': projects,
                'total_count': len(projects)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'获取失败: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': '请求方法错误'})


@login_required
def add_comment(request):
    """添加评论"""
    if request.method == 'POST':
        try:
            # 获取表单数据
            user_name = request.POST.get('user_name')
            comment_content = request.POST.get('comment_content')
            comment_grade = request.POST.get('comment_grade')
            poi_id = request.POST.get('poi_id')
            
            # 验证必填字段
            if not all([user_name, comment_content, comment_grade, poi_id]):
                return JsonResponse({'success': False, 'message': '请填写所有必填字段'})
            
            # 检查poi_id是否存在
            if not SpiderBase.objects.filter(poid=poi_id).exists():
                return JsonResponse({'success': False, 'message': '项目ID不存在'})
            
            # 创建评论
            comment = QusetAnswer.objects.create(
                comment_id=f"manual_{int(time.time())}_{random.randint(1000, 9999)}",
                user_id=random.randint(100000, 999999),
                user_name=user_name,
                comment_num=random.randint(1, 1000),
                comment_grade=comment_grade,
                comment_content=comment_content,
                poiId=poi_id,
                release_time=timezone.now(),
                create_time=timezone.now(),
                like_num=0,
                reply_num=0,
                c_num=0,
                reply_content='',
                reply_video=0,
                reply_img=0
            )
            
            return JsonResponse({'success': True, 'message': '评论添加成功', 'comment_id': comment.comment_id})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'添加失败: {str(e)}'})
    
    # GET请求，返回添加表单
    projects = SpiderBase.objects.all().order_by('IteamName')
    return render(request, 'spiders/add_comment.html', {'projects': projects})


def _grade_to_label(grade):
    """将评分（数字或字符串）转为好评/差评/中评"""
    if grade is None:
        return ''
    if isinstance(grade, str) and grade in ('好评', '差评', '中评'):
        return grade
    try:
        g = float(grade)
        if g >= 4:
            return '好评'
        if g <= 2:
            return '差评'
        return '中评'
    except (TypeError, ValueError):
        return str(grade) if grade else ''


def _label_to_grade(label):
    """将好评/差评/中评转为数字存储：好评->5, 中评->3, 差评->1"""
    if not label:
        return None
    m = {'好评': 5, '中评': 3, '差评': 1}
    return m.get(label)


@login_required
def get_comment_detail(request, comment_id):
    """获取评论详情（JSON，用于编辑弹窗）"""
    try:
        comment = QusetAnswer.objects.get(comment_id=comment_id)
    except QusetAnswer.DoesNotExist:
        return JsonResponse({'success': False, 'message': '评论不存在'})
    release_str = ''
    if comment.release_time:
        try:
            release_str = comment.release_time.strftime('%Y-%m-%dT%H:%M')
        except (ValueError, TypeError):
            release_str = ''
    grade = comment.comment_grade
    grade_label = _grade_to_label(grade)
    project_title = ''
    try:
        ps = PSentiment.objects.filter(poiId=comment.poiId).first()
        if ps:
            project_title = (ps.title or ps.itemName or '').strip()
    except Exception:
        pass
    return JsonResponse({
        'success': True,
        'comment': {
            'comment_id': comment.comment_id,
            'user_name': comment.user_name or '',
            'comment_content': comment.comment_content or '',
            'comment_grade': grade_label,
            'poiId': str(comment.poiId) if comment.poiId else '',
            'project_title': project_title,
            'release_time': release_str,
        }
    })


@login_required
def edit_comment(request, comment_id):
    """编辑评论"""
    try:
        comment = QusetAnswer.objects.get(comment_id=comment_id)
    except QusetAnswer.DoesNotExist:
        return JsonResponse({'success': False, 'message': '评论不存在'})
    
    if request.method == 'POST':
        try:
            from datetime import datetime
            # 更新评论数据
            comment.user_name = request.POST.get('user_name', comment.user_name)
            comment.comment_content = request.POST.get('comment_content', comment.comment_content)
            grade_val = request.POST.get('comment_grade', '')
            grade_num = _label_to_grade(grade_val)
            if grade_num is not None:
                comment.comment_grade = grade_num
            elif grade_val and grade_val.isdigit():
                try:
                    comment.comment_grade = float(grade_val)
                except (TypeError, ValueError):
                    pass
            comment.comment_num = request.POST.get('comment_num', comment.comment_num)

            # 发布时间
            release_time_str = request.POST.get('release_time')
            if release_time_str:
                try:
                    dt = datetime.strptime(release_time_str.replace('T', ' '), '%Y-%m-%d %H:%M')
                    comment.release_time = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                except (ValueError, TypeError):
                    pass

            # 如果poi_id有变化，验证新ID是否存在
            new_poi_id = request.POST.get('poi_id')
            if new_poi_id and new_poi_id != str(comment.poiId):
                if not SpiderBase.objects.filter(poid=new_poi_id).exists():
                    return JsonResponse({'success': False, 'message': '项目ID不存在'})
                comment.poiId = new_poi_id

            comment.save()
            
            return JsonResponse({'success': True, 'message': '评论更新成功'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'更新失败: {str(e)}'})
    
    # GET请求，返回编辑表单
    projects = SpiderBase.objects.all().order_by('IteamName')
    return render(request, 'spiders/edit_comment.html', {
        'comment': comment,
        'projects': projects
    })


@login_required
def delete_comment(request, comment_id):
    """删除评论"""
    if request.method == 'POST':
        try:
            comment = QusetAnswer.objects.get(comment_id=comment_id)
            comment.delete()
            return JsonResponse({'success': True, 'message': '评论删除成功'})
        except QusetAnswer.DoesNotExist:
            return JsonResponse({'success': False, 'message': '评论不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'删除失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def get_platform_data(request):
    """获取平台数据统计"""
    platform = request.GET.get('platform', '')
    
    if not platform:
        return JsonResponse({'success': False, 'message': '请指定平台'})
    
    try:
        # 获取该平台的poi_id列表
        platform_poi_ids = SpiderBase.objects.filter(SalesChannel=platform).values_list('poid', flat=True)
        
        # 统计该平台的评论数据
        comments = QusetAnswer.objects.filter(poiId__in=platform_poi_ids)
        
        stats = {
            'total_comments': comments.count(),
            'positive_comments': comments.filter(comment_grade__gte=4).count(),
            'negative_comments': comments.filter(comment_grade__lte=2).count(),
            'neutral_comments': comments.filter(comment_grade__gt=2, comment_grade__lt=4).count(),
            'avg_rating': comments.aggregate(avg=Avg('comment_grade'))['avg'] or 0,
            'projects': list(SpiderBase.objects.filter(SalesChannel=platform).values_list('IteamName', flat=True).distinct())
        }
        
        return JsonResponse({'success': True, 'data': stats})
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'获取数据失败: {str(e)}'})


@login_required
def get_projects_by_platform(request):
    """根据平台获取项目列表"""
    platform = request.GET.get('platform', '')
    
    if not platform:
        return JsonResponse({'success': False, 'message': '请指定平台'})
    
    try:
        # 从p_sentiment表获取该平台的项目列表
        projects = PSentiment.objects.filter(source_c=platform).values_list('title', flat=True).distinct().exclude(title__isnull=True).exclude(title='').order_by('title')
        
        return JsonResponse({
            'success': True, 
            'projects': list(projects)
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'获取项目列表失败: {str(e)}'})


# ==================== 基础表查询模块 ====================

def _basic_table_filter_query_string(search_title, search_source, search_source_type, search_user_id, page_size, sort_by='', order='desc'):
    """构建筛选/排序查询串（不含 page），供分页链接复用。"""
    from urllib.parse import urlencode
    params = {'page_size': page_size}
    if search_title:
        params['search_title'] = search_title
    if search_source:
        params['search_source'] = search_source
    if search_source_type:
        params['search_source_type'] = search_source_type
    if search_user_id:
        params['search_user_id'] = search_user_id
    if sort_by:
        params['sort_by'] = sort_by
        params['order'] = order
    return urlencode(params)


@login_required
def basic_table_query(request):
    """基础表查询主页面"""
    try:
        # 获取分页参数
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        
        # 获取筛选参数
        search_title = request.GET.get('search_title', '').strip()
        search_source = request.GET.get('search_source', '').strip()
        search_source_type = request.GET.get('search_source_type', '').strip()
        search_user_id = request.GET.get('search_user_id', '').strip()
        sort_by = request.GET.get('sort_by', '').strip()
        order = request.GET.get('order', 'desc').strip().lower()
        if order not in ('asc', 'desc'):
            order = 'desc'
        
        # 构建查询
        queryset = PSentiment.objects.all()
        
        if search_title:
            # 在多个字段中进行模糊查询：标题、项目名称等
            queryset = queryset.filter(
                Q(title__icontains=search_title) |
                Q(itemName__icontains=search_title) |
                Q(y_name__icontains=search_title)
            )
        if search_source:
            queryset = queryset.filter(source_c__icontains=search_source)
        if search_source_type:
            queryset = queryset.filter(source_type__icontains=search_source_type)
        if search_user_id:
            queryset = queryset.filter(user_id__icontains=search_user_id)
        
        # 排序：支持按评分(comment_num)、评论条数(reply_num) 升序/降序
        if sort_by == 'comment_num':
            from django.db.models import FloatField
            from django.db.models.functions import Cast
            prefix = '' if order == 'asc' else '-'
            queryset = queryset.annotate(
                _comment_num_float=Cast('comment_num', FloatField())
            ).order_by(f'{prefix}_comment_num_float', '-p_time')
        elif sort_by == 'reply_num':
            from django.db.models import F
            # 使用 F() 明确按 reply_num 数值排序
            if order == 'asc':
                queryset = queryset.order_by(F('reply_num').asc(), '-p_time')
            else:
                queryset = queryset.order_by(F('reply_num').desc(), '-p_time')
        else:
            queryset = queryset.order_by('-p_time')
        
        # 分页
        paginator = Paginator(queryset, page_size)
        try:
            records = paginator.page(page)
        except PageNotAnInteger:
            records = paginator.page(1)
        except EmptyPage:
            records = paginator.page(paginator.num_pages)
        
        # 获取统计信息
        total_count = PSentiment.objects.count()
        filtered_count = queryset.count()
        
        # 获取所有可用的来源平台和类型用于筛选
        all_sources = PSentiment.objects.values_list('source_c', flat=True).distinct().exclude(source_c__isnull=True).exclude(source_c='').order_by('source_c')
        all_source_types = PSentiment.objects.values_list('source_type', flat=True).distinct().exclude(source_type__isnull=True).exclude(source_type='').order_by('source_type')
        
        # 在视图中构建排序链接，确保参数正确传递（解决点击评论条数无图标、排序不生效）
        get_copy = request.GET.copy()
        get_copy['page'] = 1
        get_copy['page_size'] = page_size
        get_copy['sort_by'] = 'comment_num'
        get_copy['order'] = 'asc' if (sort_by == 'comment_num' and order == 'desc') else 'desc'
        sort_url_comment_num = '?' + get_copy.urlencode()
        get_copy['sort_by'] = 'reply_num'
        get_copy['order'] = 'asc' if (sort_by == 'reply_num' and order == 'desc') else 'desc'
        sort_url_reply_num = '?' + get_copy.urlencode()
        filter_query = _basic_table_filter_query_string(
            search_title, search_source, search_source_type, search_user_id,
            page_size, sort_by, order,
        )
        
        context = {
            'records': records,
            'total_count': total_count,
            'filtered_count': filtered_count,
            'all_sources': all_sources,
            'all_source_types': all_source_types,
            'search_title': search_title,
            'search_source': search_source,
            'search_user_id': search_user_id,
            'search_source_type': search_source_type,
            'page_size': page_size,
            'sort_by': sort_by,
            'order': order,
            'sort_url_comment_num': sort_url_comment_num,
            'sort_url_reply_num': sort_url_reply_num,
            'filter_query': filter_query,
        }
        
        return render(request, 'spiders/basic_table_query.html', context)
        
    except Exception as e:
        messages.error(request, f'加载数据失败: {str(e)}')
        get_copy = request.GET.copy()
        get_copy['page'] = 1
        get_copy['page_size'] = request.GET.get('page_size', 20)
        get_copy['sort_by'] = 'comment_num'
        get_copy['order'] = 'desc'
        sort_url_comment_num = '?' + get_copy.urlencode()
        get_copy['sort_by'] = 'reply_num'
        get_copy['order'] = 'desc'
        sort_url_reply_num = '?' + get_copy.urlencode()
        page_size_err = int(request.GET.get('page_size', 20))
        filter_query = _basic_table_filter_query_string(
            request.GET.get('search_title', '').strip(),
            request.GET.get('search_source', '').strip(),
            request.GET.get('search_source_type', '').strip(),
            request.GET.get('search_user_id', '').strip(),
            page_size_err,
        )
        return render(request, 'spiders/basic_table_query.html', {
            'records': [],
            'total_count': 0,
            'filtered_count': 0,
            'all_sources': [],
            'all_source_types': [],
            'search_title': request.GET.get('search_title', ''),
            'search_source': request.GET.get('search_source', ''),
            'search_user_id': request.GET.get('search_user_id', ''),
            'search_source_type': request.GET.get('search_source_type', ''),
            'page_size': page_size_err,
            'sort_by': '',
            'order': 'desc',
            'sort_url_comment_num': sort_url_comment_num,
            'sort_url_reply_num': sort_url_reply_num,
            'filter_query': filter_query,
        })


@login_required
def add_sentiment_record(request):
    """添加基础表记录"""
    if request.method == 'POST':
        try:
            # 获取表单数据，移除 null 字节等非法字符
            def _sanitize(s):
                return (s or '').replace('\x00', '').strip()

            poi_id = _sanitize(request.POST.get('poiId', ''))
            source_c = _sanitize(request.POST.get('source_c', ''))
            source_type = _sanitize(request.POST.get('source_type', ''))
            title = _sanitize(request.POST.get('title', ''))
            url = _sanitize(request.POST.get('url', ''))
            comment_num = _sanitize(request.POST.get('comment_num', '0')) or '0'
            reply_num = _sanitize(request.POST.get('reply_num', '0'))
            user_id = _sanitize(request.POST.get('user_id', ''))
            itemName = _sanitize(request.POST.get('itemName', ''))
            y_num = _sanitize(request.POST.get('y_num', ''))
            
            # 验证必填字段
            if not poi_id:
                return JsonResponse({'success': False, 'message': 'POI ID不能为空'})
            
            # 检查POI ID是否已存在
            if PSentiment.objects.filter(poiId=poi_id).exists():
                return JsonResponse({'success': False, 'message': f'POI ID "{poi_id}" 已存在，请使用不同的POI ID'})
            
            # 验证数值字段
            try:
                # 评分保留一位小数，转换为字符串格式存储
                comment_num_float = float(comment_num) if comment_num else 0.0
                comment_num_str = f"{round(comment_num_float, 1):.1f}"  # 格式化为保留一位小数的字符串
                reply_num_int = int(reply_num) if reply_num else 0
            except ValueError:
                return JsonResponse({'success': False, 'message': '评分必须是数字，评论条数必须是整数'})
            
            # 处理空字符串字段（PSentiment 的 CharField 无 null=True，需用空字符串）
            # 移除 null 字节等非法字符，避免数据库保存失败
            def clean_string_field(value):
                s = (value or '').strip()
                if isinstance(s, str):
                    s = s.replace('\x00', '')
                return s or ''
            
            # y_num 在 DB 中可能为 INT 类型，空字符串会报错
            try:
                y_num_val = int(y_num) if y_num else 0
            except (ValueError, TypeError):
                y_num_val = 0
            
            # 创建新记录
            record = PSentiment.objects.create(
                poiId=poi_id,
                source_c=clean_string_field(source_c),
                source_type=clean_string_field(source_type),
                title=clean_string_field(title),
                url=clean_string_field(url),
                comment_num=comment_num_str,  # 评分（保留一位小数的字符串格式，如"4.8"）
                reply_num=reply_num_int,  # 评论条数
                user_id=clean_string_field(user_id) or None,  # 空字符串转 None，兼容 DB 中 INT 类型
                itemName=clean_string_field(itemName),
                y_num=y_num_val,
                p_time=timezone.now()
            )
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='添加基础表记录',
                action='add_data',
                description=f'添加基础表记录: {poi_id} - {title}',
                ip_address=get_client_ip(request)
            )
            
            return JsonResponse({
                'success': True, 
                'message': '记录添加成功',
                'record_id': record.poiId
            })
            
        except ValueError as e:
            return JsonResponse({'success': False, 'message': f'数据格式错误: {str(e)}'})
        except Exception as e:
            import traceback
            print(f'添加记录错误: {str(e)}')
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'message': f'添加记录失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def update_sentiment_record(request):
    """更新基础表记录（仅 POST，poiId 从表单 body 获取，避免 URL 路径问题）"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': '无效的请求方法'})
    
    poi_id = (request.POST.get('poiId') or '').strip()
    if not poi_id:
        return JsonResponse({'success': False, 'message': 'POI ID 不能为空'})
    
    try:
        record = PSentiment.objects.get(poiId=poi_id)
    except PSentiment.DoesNotExist:
        return JsonResponse({'success': False, 'message': '记录不存在'})
    
    try:
        # 获取表单数据，移除 null 字节等非法字符
        def _sanitize(s):
            return (s or '').replace('\x00', '').strip()

        source_c = _sanitize(request.POST.get('source_c', ''))
        source_type = _sanitize(request.POST.get('source_type', ''))
        title = _sanitize(request.POST.get('title', ''))
        url = _sanitize(request.POST.get('url', ''))
        comment_num = _sanitize(request.POST.get('comment_num', '0')) or '0'
        reply_num = _sanitize(request.POST.get('reply_num', '0'))
        user_id = _sanitize(request.POST.get('user_id', ''))
        itemName = _sanitize(request.POST.get('itemName', ''))
        y_num = _sanitize(request.POST.get('y_num', ''))
        
        # 验证数值字段
        try:
            comment_num_float = float(comment_num) if comment_num else 0.0
            comment_num_str = f"{round(comment_num_float, 1):.1f}"
            reply_num_int = int(reply_num) if reply_num else 0
        except ValueError:
            return JsonResponse({'success': False, 'message': '评分必须是数字，评论条数必须是整数'})
        
        def clean_string_field(value):
            s = (value or '').strip()
            if isinstance(s, str):
                s = s.replace('\x00', '')
            return s or ''
        
        # y_num 在 DB 中可能为 INT 类型，空字符串会报错，转成 0 或 None
        try:
            y_num_val = int(y_num) if y_num else 0
        except (ValueError, TypeError):
            y_num_val = 0
        
        # 更新记录
        record.source_c = clean_string_field(source_c)
        record.source_type = clean_string_field(source_type)
        record.title = clean_string_field(title)
        record.url = clean_string_field(url)
        record.comment_num = comment_num_str
        record.reply_num = reply_num_int
        record.user_id = clean_string_field(user_id) or None  # 空字符串转 None，兼容 DB 中 INT 类型
        record.itemName = clean_string_field(itemName)
        record.y_num = y_num_val
        record.save()
        
        OperationLog.objects.create(
            user=request.user,
            operation='编辑基础表记录',
            action='edit_data',
            description=f'编辑基础表记录: {poi_id} - {title}',
            ip_address=get_client_ip(request)
        )
        
        return JsonResponse({'success': True, 'message': '记录更新成功'})
        
    except ValueError as e:
        return JsonResponse({'success': False, 'message': f'数据格式错误: {str(e)}'})
    except Exception as e:
        import traceback
        print(f'更新记录错误: {str(e)}')
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'message': f'更新记录失败: {str(e)}'})


@login_required
def edit_sentiment_record(request, poi_id):
    """编辑基础表记录（GET 返回详情，POST 也支持但推荐用 update_sentiment_record）"""
    poi_id = (poi_id or '').strip().rstrip('/')
    
    try:
        record = PSentiment.objects.get(poiId=poi_id)
    except PSentiment.DoesNotExist:
        return JsonResponse({'success': False, 'message': '记录不存在'})
    
    if request.method == 'POST':
        try:
            # 获取表单数据，移除 null 字节等非法字符
            def _sanitize(s):
                return (s or '').replace('\x00', '').strip()

            source_c = _sanitize(request.POST.get('source_c', ''))
            source_type = _sanitize(request.POST.get('source_type', ''))
            title = _sanitize(request.POST.get('title', ''))
            url = _sanitize(request.POST.get('url', ''))
            comment_num = _sanitize(request.POST.get('comment_num', '0')) or '0'
            reply_num = _sanitize(request.POST.get('reply_num', '0'))
            user_id = _sanitize(request.POST.get('user_id', ''))
            itemName = _sanitize(request.POST.get('itemName', ''))
            y_num = _sanitize(request.POST.get('y_num', ''))
            
            # 验证数值字段
            try:
                # 评分保留一位小数，转换为字符串格式存储
                comment_num_float = float(comment_num) if comment_num else 0.0
                comment_num_str = f"{round(comment_num_float, 1):.1f}"  # 格式化为保留一位小数的字符串
                reply_num_int = int(reply_num) if reply_num else 0
            except ValueError:
                return JsonResponse({'success': False, 'message': '评分必须是数字，评论条数必须是整数'})
            
            # 处理空字符串字段（PSentiment 的 CharField 无 null=True，需用空字符串而非 None）
            # 移除 null 字节等非法字符，避免数据库保存失败
            def clean_string_field(value):
                s = (value or '').strip()
                if isinstance(s, str):
                    s = s.replace('\x00', '')  # 移除 null 字节
                return s or ''
            
            # y_num 在 DB 中可能为 INT 类型，空字符串会报错
            try:
                y_num_val = int(y_num) if y_num else 0
            except (ValueError, TypeError):
                y_num_val = 0
            
            # 更新记录
            record.source_c = clean_string_field(source_c)
            record.source_type = clean_string_field(source_type)
            record.title = clean_string_field(title)
            record.url = clean_string_field(url)
            record.comment_num = comment_num_str  # 评分（保留一位小数的字符串格式，如"4.8"）
            record.reply_num = reply_num_int  # 评论条数
            record.user_id = clean_string_field(user_id) or None  # 空字符串转 None，兼容 DB 中 INT 类型
            record.itemName = clean_string_field(itemName)
            record.y_num = y_num_val
            record.save()
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='编辑基础表记录',
                action='edit_data',
                description=f'编辑基础表记录: {poi_id} - {title}',
                ip_address=get_client_ip(request)
            )
            
            return JsonResponse({
                'success': True, 
                'message': '记录更新成功'
            })
            
        except ValueError as e:
            return JsonResponse({'success': False, 'message': f'数据格式错误: {str(e)}'})
        except Exception as e:
            import traceback
            print(f'更新记录错误: {str(e)}')
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'message': f'更新记录失败: {str(e)}'})
    
    # GET请求返回记录详情（poiId 必须为字符串，避免 JS 大整数精度丢失；字段需安全序列化）
    try:
        return JsonResponse({
            'success': True,
            'record': {
                'poiId': str(record.poiId),
                'source_c': record.source_c or '',
                'source_type': record.source_type or '',
                'title': record.title or '',
                'url': record.url or '',
                'comment_num': record.comment_num or '',
                'reply_num': record.reply_num,
                'user_id': str(record.user_id) if record.user_id is not None else '',
                'y_name': record.y_name or '',
                'y_num': record.y_num or '',
                'itemName': getattr(record, 'itemName', None) or '',
                'p_time': record.p_time.strftime('%Y-%m-%d %H:%M:%S') if record.p_time else '',
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'序列化记录失败: {str(e)}'})


@login_required
def delete_sentiment_record(request, poi_id):
    """删除情感分析记录"""
    poi_id = (poi_id or '').strip().rstrip('/')
    if request.method == 'POST':
        try:
            record = PSentiment.objects.get(poiId=poi_id)
            title = record.title
            
            # 记录操作日志
            OperationLog.objects.create(
                user=request.user,
                operation='删除情感分析记录',
                action='export_data',
                description=f'删除情感分析记录: {poi_id} - {title}',
                ip_address=get_client_ip(request)
            )
            
            # 删除记录
            record.delete()
            
            return JsonResponse({
                'success': True, 
                'message': '记录删除成功'
            })
            
        except PSentiment.DoesNotExist:
            return JsonResponse({'success': False, 'message': '记录不存在'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'删除记录失败: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': '无效的请求方法'})


@login_required
def get_sentiment_record_for_edit(request):
    """获取基础表记录用于编辑（poiId 通过 GET 查询参数传递，避免 URL 路径问题）"""
    poi_id = (request.GET.get('poiId') or '').strip()
    if not poi_id:
        return JsonResponse({'success': False, 'message': 'poiId 不能为空'})
    try:
        record = PSentiment.objects.get(poiId=poi_id)
        return JsonResponse({
            'success': True,
            'record': {
                'poiId': str(record.poiId),
                'source_c': record.source_c or '',
                'source_type': record.source_type or '',
                'title': record.title or '',
                'url': record.url or '',
                'comment_num': record.comment_num or '',
                'reply_num': record.reply_num,
                'user_id': str(record.user_id) if record.user_id is not None else '',
                'y_name': record.y_name or '',
                'y_num': record.y_num or '',
                'itemName': getattr(record, 'itemName', None) or '',
                'p_time': record.p_time.strftime('%Y-%m-%d %H:%M:%S') if record.p_time else '',
            }
        })
    except PSentiment.DoesNotExist:
        return JsonResponse({'success': False, 'message': '记录不存在'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'获取记录失败: {str(e)}'})


@login_required
def get_sentiment_record_detail(request, poi_id):
    """获取情感分析记录详情"""
    poi_id = (poi_id or '').strip().rstrip('/')
    try:
        record = PSentiment.objects.get(poiId=poi_id)
        
        return JsonResponse({
            'success': True,
            'record': {
                'poiId': str(record.poiId),
                'source_c': record.source_c,
                'source_type': record.source_type,
                'title': record.title,
                'url': record.url,
                'comment_num': record.comment_num,
                'reply_num': record.reply_num,
                'user_id': record.user_id,
                'y_name': record.y_name,
                'y_num': record.y_num,
                'itemName': record.itemName if hasattr(record, 'itemName') else None,
                'p_time': record.p_time.strftime('%Y-%m-%d %H:%M:%S'),
            }
        })
        
    except PSentiment.DoesNotExist:
        return JsonResponse({'success': False, 'message': '记录不存在'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'获取记录详情失败: {str(e)}'})


@login_required
def export_sentiment_data(request):
    """导出情感分析数据"""
    try:
        # 获取筛选参数
        search_title = request.GET.get('search_title', '').strip()
        search_source = request.GET.get('search_source', '').strip()
        search_source_type = request.GET.get('search_source_type', '').strip()
        
        # 构建查询
        queryset = PSentiment.objects.all()
        
        if search_title:
            queryset = queryset.filter(title__icontains=search_title)
        if search_source:
            queryset = queryset.filter(source_c__icontains=search_source)
        if search_source_type:
            queryset = queryset.filter(source_type__icontains=search_source_type)
        
        # 排序
        queryset = queryset.order_by('-p_time')
        
        # 创建内存中的Excel文件
        output = BytesIO()
        
        # 创建Excel工作簿
        workbook = xlsxwriter.Workbook(output, {'remove_timezone': True})
        worksheet = workbook.add_worksheet('情感分析数据')
        
        # 设置标题行样式
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # 设置数据行样式
        data_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        # 设置数字格式
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '0.00'
        })
        
        # 设置日期格式
        date_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'num_format': 'yyyy-mm-dd hh:mm:ss'
        })
        
        # 设置标题行
        headers = [
            'POI ID', '来源平台', '来源类型', '标题', '链接', 
            '评论数', '回复数', '用户ID', '项目名称', '项目编号', '发布时间'
        ]
        
        # 写入标题行
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # 设置列宽
        column_widths = [12, 15, 15, 30, 40, 10, 10, 15, 20, 15, 20]
        for col, width in enumerate(column_widths):
            worksheet.set_column(col, col, width)
        
        # 写入数据
        for row, record in enumerate(queryset, 1):
            worksheet.write(row, 0, record.poiId, data_format)
            worksheet.write(row, 1, record.source_c or '', data_format)
            worksheet.write(row, 2, record.source_type or '', data_format)
            worksheet.write(row, 3, record.title or '', data_format)
            worksheet.write(row, 4, record.url or '', data_format)
            worksheet.write(row, 5, record.comment_num or 0, number_format)
            worksheet.write(row, 6, record.reply_num or 0, number_format)
            worksheet.write(row, 7, record.user_id or '', data_format)
            worksheet.write(row, 8, record.y_name or '', data_format)
            worksheet.write(row, 9, record.y_num or '', data_format)
            worksheet.write(row, 10, record.p_time, date_format)
        
        # 冻结首行
        worksheet.freeze_panes(1, 0)
        
        # 关闭工作簿
        workbook.close()
        
        # 获取Excel文件内容
        output.seek(0)
        excel_content = output.getvalue()
        
        # 创建HTTP响应
        response = HttpResponse(
            excel_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # 设置文件名
        filename = f"sentiment_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = len(excel_content)
        
        # 记录操作日志
        OperationLog.objects.create(
            user=request.user,
            operation='导出情感分析数据',
            action='export_data',
            description=f'导出情感分析数据，共{queryset.count()}条记录',
            ip_address=get_client_ip(request)
        )
        
        return response
        
    except Exception as e:
        import traceback
        error_msg = f'导出数据失败: {str(e)}\n{traceback.format_exc()}'
        print(error_msg)  # 打印到控制台用于调试
        messages.error(request, f'导出数据失败: {str(e)}')
        return redirect('basic_table_query')