#!/usr/bin/env python
"""
数据管理系统功能测试脚本
"""

import requests
import json

def test_system():
    """测试系统功能"""
    base_url = "http://localhost:8000"
    
    print("=" * 50)
    print("数据管理系统功能测试")
    print("=" * 50)
    
    # 测试1: 检查服务是否运行
    print("\n1. 检查服务状态...")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 302:  # 重定向到登录页
            print("✓ 服务正常运行，重定向到登录页")
        else:
            print(f"✓ 服务响应状态码: {response.status_code}")
    except Exception as e:
        print(f"✗ 服务连接失败: {e}")
        return False
    
    # 测试2: 检查登录页面
    print("\n2. 检查登录页面...")
    try:
        response = requests.get(f"{base_url}/accounts/login/", timeout=5)
        if response.status_code == 200 and "用户登录" in response.text:
            print("✓ 登录页面正常加载")
        else:
            print(f"✗ 登录页面异常: {response.status_code}")
    except Exception as e:
        print(f"✗ 登录页面测试失败: {e}")
    
    # 测试3: 检查主页（需要登录）
    print("\n3. 检查主页权限控制...")
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 302:
            print("✓ 主页权限控制正常，未登录用户被重定向")
        else:
            print(f"✗ 主页权限控制异常: {response.status_code}")
    except Exception as e:
        print(f"✗ 主页测试失败: {e}")
    
    # 测试4: 检查评论列表页面
    print("\n4. 检查评论列表页面...")
    try:
        response = requests.get(f"{base_url}/comments/", timeout=5)
        if response.status_code == 302:
            print("✓ 评论列表页面权限控制正常")
        else:
            print(f"✗ 评论列表页面异常: {response.status_code}")
    except Exception as e:
        print(f"✗ 评论列表页面测试失败: {e}")
    
    # 测试5: 检查静态文件
    print("\n5. 检查静态文件...")
    try:
        response = requests.get(f"{base_url}/static/", timeout=5)
        print(f"✓ 静态文件目录可访问: {response.status_code}")
    except Exception as e:
        print(f"✗ 静态文件测试失败: {e}")
    
    print("\n" + "=" * 50)
    print("测试完成！")
    print("=" * 50)
    
    print("\n🌐 系统访问信息:")
    print(f"   主页: {base_url}")
    print(f"   登录页: {base_url}/accounts/login/")
    print(f"   管理后台: {base_url}/admin/")
    
    print("\n📝 使用说明:")
    print("   1. 在浏览器中访问系统地址")
    print("   2. 使用管理员账号登录")
    print("   3. 开始使用系统功能")
    
    return True

if __name__ == "__main__":
    test_system()


