#!/usr/bin/env python3
import os
import sys
import django
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import random
import string

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spider_management.settings')
django.setup()

def test_captcha_generation():
    """测试验证码生成"""
    try:
        # 生成4位随机字符
        captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        print(f"验证码文本: {captcha_text}")
        
        # 创建图片
        width, height = 180, 60
        image = Image.new('RGB', (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(image)
        
        # 绘制背景干扰线
        for _ in range(5):
            start = (random.randint(0, width), random.randint(0, height))
            end = (random.randint(0, width), random.randint(0, height))
            draw.line([start, end], fill=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)), width=2)
        
        # 绘制验证码文字
        try:
            # 使用DejaVu字体，更大的字体大小
            font = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf", 36)
            print("✅ 使用DejaVuSans-Bold字体")
        except:
            try:
                # 备用字体
                font = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 36)
                print("✅ 使用DejaVuSans字体")
            except:
                # 最后使用默认字体
                font = ImageFont.load_default()
                print("⚠️ 使用默认字体")
        
        for i, char in enumerate(captcha_text):
            x = 10 + i * 30
            y = 5
            color = (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
            draw.text((x, y), char, font=font, fill=color)
        
        # 保存测试图片
        image.save('/tmp/test_captcha.png')
        print(f"✅ 验证码图片已保存到 /tmp/test_captcha.png")
        print(f"✅ 图片尺寸: {width}x{height}")
        print(f"✅ 字体大小: 36px")
        
        return True
    except Exception as e:
        print(f"❌ 验证码生成失败: {e}")
        return False

if __name__ == "__main__":
    success = test_captcha_generation()
    if success:
        print("✅ 验证码生成测试通过")
    else:
        print("❌ 验证码生成测试失败")

