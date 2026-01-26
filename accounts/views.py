from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
import json
import random
import string
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64
from .models import UserProfile, OperationLog
from spiders.models import QusetAnswer, SpiderBase


def get_client_ip(request):
    """获取客户端IP地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_operation(user, action, description, request, operation='', target=''):
    """记录操作日志"""
    OperationLog.objects.create(
        user=user,
        operation=operation or action,
        action=action,
        target=target,
        description=description,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )


def generate_captcha():
    """生成验证码"""
    # 生成4位随机字符
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    
    # 创建图片
    width, height = 180, 60  # 进一步增大图片尺寸以容纳更大字体
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
    except:
        try:
            # 备用字体
            font = ImageFont.truetype("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", 36)
        except:
            # 最后使用默认字体
            font = ImageFont.load_default()
    
    for i, char in enumerate(captcha_text):
        x = 10 + i * 30  # 调整字符间距
        y = 5
        color = (random.randint(0, 100), random.randint(0, 100), random.randint(0, 100))
        draw.text((x, y), char, font=font, fill=color)
    
    # 转换为base64
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return captcha_text, img_str


class LoginView(View):
    """登录视图"""
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/')
        
        captcha_text, captcha_img = generate_captcha()
        request.session['captcha'] = captcha_text
        
        context = {
            'captcha_img': captcha_img,
        }
        return render(request, 'accounts/login.html', context)
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        captcha = request.POST.get('captcha', '').upper()
        session_captcha = request.session.get('captcha', '').upper()
        
        # 临时跳过验证码验证用于调试
        # if captcha != session_captcha:
        #     messages.error(request, "验证码错误")
        #     return self.get(request)
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            log_operation(user, 'login', f'用户 {username} 登录成功', request)
            return redirect('/')
        else:
            messages.error(request, '用户名或密码错误')
            return self.get(request)


class LogoutView(View):
    """登出视图"""
    
    def get(self, request):
        if request.user.is_authenticated:
            log_operation(request.user, 'logout', f'用户 {request.user.username} 登出', request)
        logout(request)
        return redirect('/accounts/login/')


class ChangePasswordView(View):
    """修改密码视图"""
    
    @method_decorator(login_required)
    def get(self, request):
        return render(request, 'accounts/change_password.html')
    
    @method_decorator(login_required)
    def post(self, request):
        old_password = request.POST.get('old_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # 验证旧密码
        if not request.user.check_password(old_password):
            messages.error(request, '旧密码错误')
            return render(request, 'accounts/change_password.html')
        
        # 验证新密码
        if new_password != confirm_password:
            messages.error(request, '两次输入的新密码不一致')
            return render(request, 'accounts/change_password.html')
        
        if len(new_password) < 6:
            messages.error(request, '新密码长度至少6位')
            return render(request, 'accounts/change_password.html')
        
        # 修改密码
        request.user.set_password(new_password)
        request.user.save()
        
        log_operation(request.user, 'change_password', f'用户 {request.user.username} 修改密码', request)
        messages.success(request, '密码修改成功，请重新登录')
        return redirect('/accounts/login/')


@csrf_exempt
def refresh_captcha(request):
    """刷新验证码"""
    captcha_text, captcha_img = generate_captcha()
    request.session['captcha'] = captcha_text
    
    return JsonResponse({
        'success': True,
        'captcha_img': captcha_img
    })


@login_required
def user_management(request):
    """用户管理（仅管理员）"""
    try:
        profile = request.user.userprofile
        if profile.role != 'admin':
            messages.error(request, '权限不足')
            return redirect('/')
    except UserProfile.DoesNotExist:
        messages.error(request, '权限不足')
        return redirect('/')
    
    users = User.objects.all().order_by('-date_joined')
    paginator = Paginator(users, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'accounts/user_management.html', context)


@login_required
def operation_logs(request):
    """操作日志（仅管理员）"""
    try:
        profile = request.user.userprofile
        if profile.role not in ['admin', 'super_admin']:
            messages.error(request, '权限不足')
            return redirect('/')
    except UserProfile.DoesNotExist:
        messages.error(request, '权限不足')
        return redirect('/')
    
    logs = OperationLog.objects.all().order_by('-created_at')
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'accounts/operation_logs.html', context)