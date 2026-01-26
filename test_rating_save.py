#!/usr/bin/env python3
"""测试评分保存功能"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

from spiders.models import PSentiment
from django.utils import timezone
import time

print('=' * 70)
print('测试评分保存功能')
print('=' * 70)

# 测试用例
test_cases = [
    ('test_rating_1', '4.8', '应该保存为4.8'),
    ('test_rating_2', '4.75', '应该保存为4.8（四舍五入）'),
    ('test_rating_3', '5', '应该保存为5.0'),
    ('test_rating_4', '4.99', '应该保存为5.0（四舍五入）'),
]

# 格式化函数（与views.py中的逻辑一致）
def format_rating(comment_num):
    try:
        comment_num_float = float(comment_num) if comment_num else 0.0
        comment_num_str = f"{round(comment_num_float, 1):.1f}"
        return comment_num_str
    except ValueError:
        return None

print('\n1. 测试格式化逻辑:')
for poi_id, input_val, desc in test_cases:
    formatted = format_rating(input_val)
    print(f'   {desc}')
    print(f'   输入: {input_val} → 格式化: {formatted}')
    
    # 检查是否已存在测试记录
    if PSentiment.objects.filter(poiId=poi_id).exists():
        PSentiment.objects.filter(poiId=poi_id).delete()
        print(f'   已删除旧测试记录')
    
    # 创建测试记录
    try:
        record = PSentiment.objects.create(
            poiId=poi_id,
            comment_num=formatted,
            reply_num=100,
            p_time=timezone.now()
        )
        
        # 验证保存结果
        saved_record = PSentiment.objects.get(poiId=poi_id)
        saved_value = saved_record.comment_num
        print(f'   保存到数据库: {saved_value} (类型: {type(saved_value).__name__})')
        
        if str(saved_value) == formatted:
            print(f'   ✅ 保存正确！\n')
        else:
            print(f'   ❌ 保存错误！期望: {formatted}, 实际: {saved_value}\n')
            
    except Exception as e:
        print(f'   ❌ 创建记录失败: {e}\n')

print('=' * 70)
print('✅ 测试完成！')
print('=' * 70)

# 清理测试数据
print('\n清理测试数据...')
for poi_id, _, _ in test_cases:
    PSentiment.objects.filter(poiId=poi_id).delete()
print('✅ 清理完成')



