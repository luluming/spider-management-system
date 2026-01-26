#!/usr/bin/env python
"""
测试修复后的系统
Author: stone
"""

import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from accounts.models import OperationLog
from django.contrib.auth.models import User

def test_operation_log():
    """测试操作日志创建"""
    
    print("=" * 50)
    print("测试OperationLog模型修复")
    print("=" * 50)
    
    try:
        # 获取一个用户进行测试
        user = User.objects.first()
        if not user:
            print("❌ 没有找到用户，无法测试")
            return False
        
        print(f"✓ 使用用户: {user.username}")
        
        # 测试创建操作日志
        log = OperationLog.objects.create(
            user=user,
            operation='测试操作',
            action='view_data',
            target='测试目标',
            description='这是一个测试操作日志',
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )
        
        print(f"✓ 成功创建操作日志: ID={log.id}")
        print(f"  操作名称: {log.operation}")
        print(f"  操作类型: {log.action}")
        print(f"  目标对象: {log.target}")
        print(f"  描述: {log.description}")
        print(f"  IP地址: {log.ip_address}")
        print(f"  创建时间: {log.created_at}")
        
        # 清理测试数据
        log.delete()
        print("✓ 测试数据已清理")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_database_connection():
    """测试数据库连接"""
    
    print("\n" + "=" * 50)
    print("测试数据库连接")
    print("=" * 50)
    
    try:
        from spiders.models import QusetAnswer, PSentiment, SpiderBase
        
        # 测试基础查询
        comment_count = QusetAnswer.objects.count()
        sentiment_count = PSentiment.objects.count()
        project_count = SpiderBase.objects.count()
        
        print(f"✓ 评论数据: {comment_count:,} 条")
        print(f"✓ 情感数据: {sentiment_count:,} 条")
        print(f"✓ 项目数据: {project_count:,} 条")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接测试失败: {e}")
        return False

def test_web_endpoints():
    """测试Web端点"""
    
    print("\n" + "=" * 50)
    print("测试Web端点")
    print("=" * 50)
    
    import requests
    
    base_url = "http://localhost:8000"
    
    try:
        # 测试登录页面
        response = requests.get(f"{base_url}/accounts/login/", timeout=10)
        print(f"✓ 登录页面: {response.status_code}")
        
        # 测试主页重定向
        response = requests.get(f"{base_url}/", timeout=10, allow_redirects=False)
        print(f"✓ 主页重定向: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"❌ Web端点测试失败: {e}")
        return False

if __name__ == '__main__':
    print("数据管理系统修复验证")
    print(f"测试时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success_count = 0
    total_tests = 3
    
    # 测试数据库连接
    if test_database_connection():
        success_count += 1
    
    # 测试操作日志
    if test_operation_log():
        success_count += 1
    
    # 测试Web端点
    if test_web_endpoints():
        success_count += 1
    
    print("\n" + "=" * 50)
    print("测试结果汇总")
    print("=" * 50)
    print(f"通过测试: {success_count}/{total_tests}")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！系统修复成功！")
        sys.exit(0)
    else:
        print("⚠️  部分测试失败，请检查系统状态")
        sys.exit(1)




