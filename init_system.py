#!/usr/bin/env python
"""
数据管理系统初始化脚本
用于创建数据库、迁移数据、创建超级用户等
"""

import os
import sys
import django
from django.core.management import execute_from_command_line
from django.contrib.auth.models import User
from django.db import connection
from datetime import datetime, timedelta
import random

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from accounts.models import UserProfile, OperationLog
from spiders.models import QusetAnswer, SpiderBase, PSentiment


def create_database():
    """创建数据库"""
    print("正在创建数据库...")
    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS spider_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("数据库创建成功！")
    except Exception as e:
        print(f"数据库创建失败: {e}")


def run_migrations():
    """运行数据库迁移"""
    print("正在运行数据库迁移...")
    try:
        execute_from_command_line(['manage.py', 'migrate'])
        print("数据库迁移完成！")
    except Exception as e:
        print(f"数据库迁移失败: {e}")


def create_superuser():
    """创建超级用户"""
    print("正在创建超级用户...")
    try:
        if not User.objects.filter(username='admin').exists():
            user = User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='admin123'
            )
            # 创建用户扩展信息
            UserProfile.objects.create(
                user=user,
                role='admin',
                department='技术部',
                phone='13800138000'
            )
            print("超级用户创建成功！用户名: admin, 密码: admin123")
        else:
            print("超级用户已存在")
    except Exception as e:
        print(f"超级用户创建失败: {e}")


def create_sample_data():
    """创建示例数据"""
    print("正在创建示例数据...")
    
    # 平台列表
    platforms = ['去哪儿', '同程', '大众点评', '抖音', '携程', '美团', '飞猪', '驴妈妈']
    
    # 项目名称
    projects = [
        '北京故宫博物院', '上海迪士尼乐园', '杭州西湖', '成都大熊猫基地',
        '西安兵马俑', '桂林山水', '张家界国家森林公园', '九寨沟',
        '黄山风景区', '泰山风景区', '华山风景区', '峨眉山',
        '三亚亚龙湾', '厦门鼓浪屿', '青岛崂山', '大连星海广场'
    ]
    
    # 用户名
    usernames = [
        '张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十',
        '郑十一', '王十二', '冯十三', '陈十四', '褚十五', '卫十六',
        '蒋十七', '沈十八', '韩十九', '杨二十', '朱二一', '秦二二'
    ]
    
    # 评论内容模板
    comment_templates = [
        "这个地方真的很不错，环境优美，服务也很好！",
        "性价比很高，值得推荐给大家。",
        "风景很美，但是人太多了，建议错峰出行。",
        "服务态度很好，设施也比较完善。",
        "价格有点贵，但是体验还是不错的。",
        "交通很方便，位置也很好找。",
        "适合带小朋友来玩，孩子很喜欢。",
        "景色很美，拍照很出片。",
        "管理很规范，安全措施做得很好。",
        "推荐指数五颗星，下次还会再来。"
    ]
    
    try:
        # 创建基础数据
        for i, project in enumerate(projects):
            platform = random.choice(platforms)
            SpiderBase.objects.get_or_create(
                poiId=f"POI_{i+1:03d}",
                defaults={
                    'poiName': project,
                    'source_c': platform,
                    'city': random.choice(['北京', '上海', '杭州', '成都', '西安', '桂林', '张家界', '九寨沟']),
                    'address': f"{random.choice(['北京市', '上海市', '杭州市', '成都市'])}{random.choice(['朝阳区', '海淀区', '西城区', '东城区'])}{random.choice(['某某街道', '某某路', '某某广场'])}"
                }
            )
        
        # 创建评论数据
        for i in range(1000):  # 创建1000条评论
            project = random.choice(projects)
            platform = random.choice(platforms)
            username = random.choice(usernames)
            rating = random.randint(1, 5)
            comment_content = random.choice(comment_templates)
            
            # 随机生成发布时间（最近30天内）
            publish_time = datetime.now() - timedelta(days=random.randint(0, 30))
            
            QusetAnswer.objects.create(
                poiId=f"POI_{random.randint(1, len(projects)):03d}",
                poiName=project,
                source_c=platform,
                userName=username,
                userAvatar=f"https://via.placeholder.com/50x50?text={username[0]}",
                content=comment_content,
                rating=rating,
                likeCount=random.randint(0, 100),
                replyCount=random.randint(0, 20),
                publishTime=publish_time
            )
        
        print(f"示例数据创建完成！创建了 {len(projects)} 个项目，1000 条评论")
        
    except Exception as e:
        print(f"示例数据创建失败: {e}")


def main():
    """主函数"""
    print("=" * 50)
    print("数据管理系统初始化脚本")
    print("=" * 50)
    
    # 检查是否需要创建数据库
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        print("数据库连接失败，请确保MySQL服务已启动")
        return
    
    # 创建数据库
    create_database()
    
    # 运行迁移
    run_migrations()
    
    # 创建超级用户
    create_superuser()
    
    # 创建示例数据
    create_sample_data()
    
    print("=" * 50)
    print("初始化完成！")
    print("请使用以下信息登录系统：")
    print("用户名: admin")
    print("密码: admin123")
    print("=" * 50)


if __name__ == '__main__':
    main()


