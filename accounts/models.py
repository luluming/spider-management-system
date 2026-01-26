from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """用户扩展信息表"""
    ROLE_CHOICES = [
        ('user', '普通用户'),
        ('admin', '管理员'),
        ('super_admin', '超级管理员'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='用户')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user', verbose_name='角色')
    department = models.CharField(max_length=100, verbose_name='部门', blank=True, null=True)
    phone = models.CharField(max_length=20, verbose_name='电话', blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', verbose_name='头像', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'user_profile'
        verbose_name = '用户扩展信息'
        verbose_name_plural = '用户扩展信息'

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class OperationLog(models.Model):
    """操作日志表"""
    ACTION_CHOICES = [
        ('login', '登录'),
        ('logout', '登出'),
        ('change_password', '修改密码'),
        ('view_data', '查看数据'),
        ('export_data', '导出数据'),
        ('create', '创建记录'),
        ('update', '更新记录'),
        ('delete', '删除记录'),
        ('add_data', '新增数据'),
        ('edit_data', '编辑数据'),
        ('create_user', '创建用户'),
        ('edit_user', '编辑用户'),
        ('delete_user', '删除用户'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    operation = models.CharField(max_length=100, verbose_name='操作名称', default='')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name='操作类型')
    target = models.CharField(max_length=100, verbose_name='目标对象', default='')
    target_id = models.CharField(max_length=50, verbose_name='目标ID', blank=True, null=True)
    details = models.TextField(verbose_name='详细信息', blank=True, null=True)
    description = models.TextField(verbose_name='操作描述')
    ip_address = models.GenericIPAddressField(verbose_name='IP地址')
    user_agent = models.TextField(verbose_name='用户代理', blank=True, null=True)
    operation_time = models.DateTimeField(auto_now_add=True, verbose_name='操作时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'operation_log'
        verbose_name = '操作日志'
        verbose_name_plural = '操作日志'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.created_at}"