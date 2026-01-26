#!/usr/bin/env python3
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from spiders.models import QusetAnswer, SpiderBase

def test_model_properties():
    """测试模型属性"""
    try:
        # 测试QusetAnswer的poiId属性
        if QusetAnswer.objects.exists():
            comment = QusetAnswer.objects.first()
            print(f"QusetAnswer.poiId: {comment.poiId}")
            print(f"QusetAnswer.poiName: {comment.poiName}")
            print(f"QusetAnswer.source_c: {comment.source_c}")
        else:
            print("QusetAnswer表中没有数据")
        
        # 测试SpiderBase的poiId属性
        if SpiderBase.objects.exists():
            base = SpiderBase.objects.first()
            print(f"SpiderBase.poiId: {base.poiId}")
            print(f"SpiderBase.poiName: {base.poiName}")
            print(f"SpiderBase.source_c: {base.source_c}")
        else:
            print("SpiderBase表中没有数据")
        
        return True
    except Exception as e:
        print(f"测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_model_properties()
    if success:
        print("✅ 模型属性测试通过")
    else:
        print("❌ 模型属性测试失败")

