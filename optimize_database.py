#!/usr/bin/env python
"""
数据库性能优化脚本
Author: stone
"""

import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from django.db import connection

def create_indexes():
    """创建性能优化索引"""
    
    indexes = [
        # PSentiment表索引
        "CREATE INDEX IF NOT EXISTS idx_psentiment_p_time ON p_sentiment (p_time);",
        "CREATE INDEX IF NOT EXISTS idx_psentiment_source_c ON p_sentiment (source_c);",
        "CREATE INDEX IF NOT EXISTS idx_psentiment_poiId ON p_sentiment (poiId);",
        "CREATE INDEX IF NOT EXISTS idx_psentiment_title ON p_sentiment (title);",
        "CREATE INDEX IF NOT EXISTS idx_psentiment_p_time_date ON p_sentiment (DATE(p_time));",
        "CREATE INDEX IF NOT EXISTS idx_psentiment_source_poi ON p_sentiment (source_c, poiId);",
        
        # QusetAnswer表索引
        "CREATE INDEX IF NOT EXISTS idx_quset_release_time ON quset_answer (release_time);",
        "CREATE INDEX IF NOT EXISTS idx_quset_poiId ON quset_answer (poiId);",
        "CREATE INDEX IF NOT EXISTS idx_quset_user_name ON quset_answer (user_name);",
        "CREATE INDEX IF NOT EXISTS idx_quset_comment_grade ON quset_answer (comment_grade);",
        "CREATE INDEX IF NOT EXISTS idx_quset_like_num ON quset_answer (like_num);",
        "CREATE INDEX IF NOT EXISTS idx_quset_reply_num ON quset_answer (reply_num);",
        "CREATE INDEX IF NOT EXISTS idx_quset_release_date ON quset_answer (DATE(release_time));",
        "CREATE INDEX IF NOT EXISTS idx_quset_poi_grade ON quset_answer (poiId, comment_grade);",
        
        # SpiderBase表索引
        "CREATE INDEX IF NOT EXISTS idx_spider_SalesChannel ON spider_base (SalesChannel);",
        "CREATE INDEX IF NOT EXISTS idx_spider_IteamName ON spider_base (IteamName);",
        "CREATE INDEX IF NOT EXISTS idx_spider_poid ON spider_base (poid);",
        "CREATE INDEX IF NOT EXISTS idx_spider_channel_item ON spider_base (SalesChannel, IteamName);",
    ]
    
    print("开始创建数据库索引...")
    
    with connection.cursor() as cursor:
        for i, index_sql in enumerate(indexes, 1):
            try:
                cursor.execute(index_sql)
                print(f"✓ 索引 {i}/{len(indexes)} 创建成功")
            except Exception as e:
                print(f"✗ 索引 {i} 创建失败: {e}")
    
    print("数据库索引创建完成！")

def analyze_tables():
    """分析表统计信息"""
    
    tables = ['p_sentiment', 'quset_answer', 'spider_base']
    
    print("\n开始分析表统计信息...")
    
    with connection.cursor() as cursor:
        for table in tables:
            try:
                cursor.execute(f"ANALYZE TABLE {table};")
                print(f"✓ 表 {table} 分析完成")
            except Exception as e:
                print(f"✗ 表 {table} 分析失败: {e}")

def show_indexes():
    """显示当前索引"""
    
    tables = ['p_sentiment', 'quset_answer', 'spider_base']
    
    print("\n当前数据库索引:")
    
    with connection.cursor() as cursor:
        for table in tables:
            print(f"\n=== {table} 表索引 ===")
            cursor.execute(f"SHOW INDEX FROM {table};")
            indexes = cursor.fetchall()
            
            for index in indexes:
                print(f"  - {index[2]} ({index[4]})")

if __name__ == '__main__':
    print("=" * 50)
    print("数据库性能优化脚本")
    print("=" * 50)
    
    try:
        # 创建索引
        create_indexes()
        
        # 分析表
        analyze_tables()
        
        # 显示索引
        show_indexes()
        
        print("\n" + "=" * 50)
        print("数据库优化完成！")
        print("=" * 50)
        
    except Exception as e:
        print(f"优化过程中出现错误: {e}")
        sys.exit(1)




