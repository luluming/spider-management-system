#!/usr/bin/env python
"""
数据管理系统测试脚本
用于验证系统基本功能是否正常
"""

import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from accounts.models import UserProfile, OperationLog
from spiders.models import QusetAnswer, SpiderBase


def test_database_connection():
    """测试数据库连接"""
    print("测试数据库连接...")
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✓ 数据库连接正常")
        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False


def test_models():
    """测试数据模型"""
    print("测试数据模型...")
    try:
        # 测试User模型
        user_count = User.objects.count()
        print(f"✓ User模型正常，当前用户数: {user_count}")
        
        # 测试UserProfile模型
        profile_count = UserProfile.objects.count()
        print(f"✓ UserProfile模型正常，当前配置数: {profile_count}")
        
        # 测试QusetAnswer模型
        comment_count = QusetAnswer.objects.count()
        print(f"✓ QusetAnswer模型正常，当前评论数: {comment_count}")
        
        # 测试SpiderBase模型
        base_count = SpiderBase.objects.count()
        print(f"✓ SpiderBase模型正常，当前项目数: {base_count}")
        
        return True
    except Exception as e:
        print(f"✗ 数据模型测试失败: {e}")
        return False


def test_urls():
    """测试URL配置"""
    print("测试URL配置...")
    try:
        from django.urls import reverse
        
        # 测试主要URL
        urls_to_test = [
            ('login', 'login'),
            ('dashboard', 'dashboard'),
            ('comments_list', 'comments_list'),
        ]
        
        for name, url_name in urls_to_test:
            try:
                url = reverse(url_name)
                print(f"✓ {name} URL正常: {url}")
            except Exception as e:
                print(f"✗ {name} URL失败: {e}")
                return False
        
        return True
    except Exception as e:
        print(f"✗ URL配置测试失败: {e}")
        return False


def test_views():
    """测试视图功能"""
    print("测试视图功能...")
    try:
        client = Client()
        
        # 测试登录页面
        response = client.get('/accounts/login/')
        if response.status_code == 200:
            print("✓ 登录页面正常")
        else:
            print(f"✗ 登录页面失败: {response.status_code}")
            return False
        
        # 测试主页（需要登录）
        response = client.get('/')
        if response.status_code == 302:  # 重定向到登录页
            print("✓ 主页权限控制正常")
        else:
            print(f"✗ 主页权限控制异常: {response.status_code}")
            return False
        
        return True
    except Exception as e:
        print(f"✗ 视图功能测试失败: {e}")
        return False


def test_templates():
    """测试模板文件"""
    print("测试模板文件...")
    try:
        template_files = [
            'templates/base.html',
            'templates/accounts/login.html',
            'templates/accounts/change_password.html',
            'templates/spiders/dashboard.html',
            'templates/spiders/comments_list.html',
            'templates/spiders/comments_list_content.html',
            'templates/accounts/user_management.html',
            'templates/accounts/operation_logs.html',
        ]
        
        for template_file in template_files:
            if os.path.exists(template_file):
                print(f"✓ {template_file} 存在")
            else:
                print(f"✗ {template_file} 不存在")
                return False
        
        return True
    except Exception as e:
        print(f"✗ 模板文件测试失败: {e}")
        return False


def test_static_files():
    """测试静态文件目录"""
    print("测试静态文件目录...")
    try:
        static_dirs = [
            'static',
            'static/css',
            'static/js',
            'static/images',
        ]
        
        for static_dir in static_dirs:
            if os.path.exists(static_dir):
                print(f"✓ {static_dir} 目录存在")
            else:
                print(f"✗ {static_dir} 目录不存在")
                return False
        
        return True
    except Exception as e:
        print(f"✗ 静态文件测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("=" * 50)
    print("数据管理系统功能测试")
    print("=" * 50)
    
    tests = [
        ("数据库连接", test_database_connection),
        ("数据模型", test_models),
        ("URL配置", test_urls),
        ("视图功能", test_views),
        ("模板文件", test_templates),
        ("静态文件", test_static_files),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} 测试失败")
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统可以正常启动")
        print("\n启动命令:")
        print("python manage.py runserver 0.0.0.0:8000")
        print("或使用: ./start.sh")
    else:
        print("⚠️  部分测试失败，请检查相关配置")
    
    print("=" * 50)


if __name__ == '__main__':
    main()
