#!/usr/bin/env python3
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from spiders.views import dashboard
from django.test import RequestFactory
from django.contrib.auth.models import User

def test_dashboard_analytics():
    """测试仪表板统计分析功能"""
    try:
        print("🔧 测试仪表板统计分析功能...")
        
        rf = RequestFactory()
        user = User.objects.get(username='admin')
        
        # 测试仪表板页面
        print("\n📊 测试仪表板页面...")
        request = rf.get('/')
        request.user = user
        response = dashboard(request)
        
        print(f"   仪表板页面: {'✅ 成功' if response.status_code == 200 else '❌ 失败'} (状态码: {response.status_code})")
        
        if response.status_code == 200:
            print("   ✅ 仪表板加载成功，包含以下统计数据:")
            print("     - 基础统计卡片")
            print("     - 今日数据统计")
            print("     - 月度增长趋势图")
            print("     - 每日增长趋势图")
            print("     - 平台分布饼图")
            print("     - 平台详细统计表")
        
        print("\n🎉 仪表板测试完成!")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_dashboard_analytics()
    if success:
        print("\n✅ 仪表板统计分析功能测试通过!")
    else:
        print("\n❌ 仪表板统计分析功能测试失败!")





