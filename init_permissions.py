#!/usr/bin/env python
"""
初始化用户权限系统脚本
"""

import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from django.contrib.auth.models import User
from django.core.management import execute_from_command_line

def init_permissions():
    """初始化权限系统"""
    print("🚀 正在初始化用户权限系统...")
    
    # 创建迁移文件（仅添加新模型的表）
    print("📁 创建数据库迁移...")
    execute_from_command_line(['manage.py', 'makemigrations', 'spiders'])
    
    # 执行迁移
    print("🗄️ 执行数据库迁移...")
    execute_from_command_line(['manage.py', 'migrate', 'spiders'])
    
    # 为现有用户创建权限配置
    print("👥 为用户创建权限配置...")
    from spiders.models import UserPermissionProfile
    
    for user in User.objects.all():
        profile, created = UserPermissionProfile.objects.get_or_create(
            user=user,
            defaults={
                'permission_level': 'senior_analyst' if user.is_superuser else 'analyst'
            }
        )
        if created:
            print(f"✅ 为用户 {user.username} 创建了权限配置")
        else:
            print(f"ℹ️ 用户 {user.username} 已有权限配置")
    
    # 创建默认权限模板
    print("📋 创建默认权限模板...")
    from spiders.models import SystemPermission
    
    templates = [
        {
            'name': '基础用户',
            'description': '只能查看基础情感分析数据',
            'permission_level': 'basic',
            'can_view_basic_sentiment': True,
            'can_view_advanced_sentiment': False,
            'can_export_data': False,
            'can_manage_users': False,
            'can_system_settings': False,
        },
        {
            'name': '情感分析师',
            'description': '可以查看基础情感分析并具有基本导出功能',
            'permission_level': 'analyst',
            'can_view_basic_sentiment': True,
            'can_view_advanced_sentiment': False,
            'can_export_data': True,
            'can_manage_users': False,
            'can_system_settings': False,
        },
        {
            'name': '高级分析师',
            'description': '可以查看和操作所有情感分析功能',
            'permission_level': 'senior_analyst',
            'can_view_basic_sentiment': True,
            'can_view_advanced_sentiment': True,
            'can_export_data': True,
            'can_manage_users': False,
            'can_system_settings': False,
        },
    ]
    
    for template_data in templates:
        template, created = SystemPermission.objects.get_or_create(
            name=template_data['name'],
            defaults={
                'description': template_data['description'],
                'can_view_basic_sentiment': template_data['can_view_basic_sentiment'],
                'can_view_advanced_sentiment': template_data['can_view_advanced_sentiment'],
                'can_export_data': template_data['can_export_data'],
                'can_manage_users': template_data['can_manage_users'],
                'can_system_settings': template_data['can_system_settings'],
            }
        )
        if created:
            print(f"✅ 创建权限模板: {template.name}")
        else:
            print(f"ℹ️ 权限模板已存在: {template.name}")
    
    print("🎉 权限系统初始化完成！")
    print("\n📝 使用说明:")
    print("- 访问 /permission-management/ 进行用户权限管理")
    print("- 访问 /sentiment-analysis/ 查看情感分析功能（需要基础权限）")
    print("- 超级用户可以访问所有功能")
    print("- 普通用户默认为基础权限级别")

if __name__ == '__main__':
    init_permissions()
