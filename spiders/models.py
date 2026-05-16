from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.utils import timezone

class SpiderBase(models.Model):
    """爬虫基础数据表"""
    id = models.AutoField(primary_key=True)
    SalesChannel = models.CharField(max_length=255, blank=True, null=True, db_column='SalesChannel')
    industry = models.CharField(max_length=255, blank=True, null=True)
    request_data = models.TextField(db_column='request_data')
    project_id = models.CharField(max_length=100, blank=True, null=True)
    IteamName = models.CharField(max_length=255, blank=True, null=True, db_column='IteamName')
    IteamState = models.CharField(max_length=255, blank=True, null=True)
    poid = models.BigIntegerField(blank=True, null=True, db_column='poid')
    sort_type = models.CharField(max_length=10, blank=True, null=True)
    total_collection_page = models.IntegerField(blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)
    created_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, blank=True, null=True, db_column='created_by_id')

    class Meta:
        db_table = 'spider_base'

    def __str__(self):
        return f"{self.IteamName} - {self.SalesChannel}"
    
    @property
    def title(self):
        """兼容性属性：返回IteamName作为title"""
        return self.IteamName or ''
    
    @property
    def platform(self):
        """兼容性属性：返回SalesChannel作为platform"""
        return self.SalesChannel or ''
    
    @property
    def url(self):
        """兼容性属性：从request_data中提取URL"""
        if self.request_data:
            try:
                import json
                data = json.loads(self.request_data)
                return data.get('url', '')
            except:
                return ''
        return ''
    
    @property
    def status(self):
        """兼容性属性：返回IteamState作为status"""
        return self.normalized_state

    _STATE_ACTIVE_VALUES = frozenset({
        'active', '激活', '启用', '1', 'true', 'on', 'running', '运行',
    })
    _STATE_INACTIVE_VALUES = frozenset({
        'inactive', '关闭', '停用', '0', 'false', 'off', 'disabled', 'paused', '暂停',
    })

    @classmethod
    def normalize_state(cls, value):
        """将库内各种状态值统一为 active / inactive；空值视为激活。"""
        if value is None:
            return 'active'
        raw = str(value).strip()
        if not raw:
            return 'active'
        lowered = raw.lower()
        if raw in cls._STATE_INACTIVE_VALUES or lowered in cls._STATE_INACTIVE_VALUES:
            return 'inactive'
        if raw in cls._STATE_ACTIVE_VALUES or lowered in cls._STATE_ACTIVE_VALUES:
            return 'active'
        return 'active'

    @property
    def normalized_state(self):
        return self.normalize_state(self.IteamState)

    @property
    def is_config_active(self):
        return self.normalized_state == 'active'

    @property
    def state_label(self):
        return '激活' if self.is_config_active else '关闭'

    def toggle_config_state(self):
        """在激活与关闭之间切换，返回新状态（active/inactive）。"""
        new_state = 'inactive' if self.is_config_active else 'active'
        self.IteamState = new_state
        self.save(update_fields=['IteamState', 'updated_at'])
        return new_state


class QusetAnswer(models.Model):
    """用户问答评论表"""
    comment_id = models.CharField(max_length=255, primary_key=True)
    poiId = models.CharField(max_length=255, db_column='poiId')
    user_name = models.CharField(max_length=255, blank=True)
    comment_content = models.TextField(blank=True)
    comment_grade = models.FloatField(default=0.0)
    like_num = models.IntegerField(default=0)
    reply_num = models.IntegerField(default=0)
    release_time = models.DateTimeField()
    user_id = models.CharField(max_length=255, blank=True)
    comment_num = models.IntegerField(default=0)

    class Meta:
        db_table = 'quset_answer'
        managed = True

    def __str__(self):
        return f"Comment {self.comment_id}"


class PSentiment(models.Model):
    """情感分析数据表"""
    poiId = models.CharField(max_length=255, primary_key=True)
    source_c = models.CharField(max_length=100, blank=True)
    source_type = models.CharField(max_length=100, blank=True) 
    title = models.CharField(max_length=255, blank=True)
    url = models.CharField(max_length=500, blank=True)
    p_time = models.DateTimeField()
    comment_num = models.CharField(max_length=20, default='0.0', blank=True, help_text='评分（保留一位小数，如4.8）')
    reply_num = models.IntegerField(default=0)
    user_id = models.CharField(max_length=255, blank=True)
    y_name = models.CharField(max_length=255, blank=True)
    y_num = models.CharField(max_length=255, blank=True)
    itemName = models.CharField(max_length=255, blank=True, db_column='itemName')

    class Meta:
        db_table = 'p_sentiment'

    def __str__(self):
        return f"{self.title} - {self.source_c}"


class UserPermissionProfile(models.Model):
    """用户权限配置表"""
    PERMISSION_LEVEL_CHOICES = [
        ('basic', '基础用户'),
        ('analyst', '情感分析师'), 
        ('senior_analyst', '高级分析师'),
        ('admin', '系统管理员'),
        ('super_admin', '超级管理员'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='permission_profile')
    permission_level = models.CharField(max_length=20, choices=PERMISSION_LEVEL_CHOICES, default='basic')
    
    # 具体权限控制
    can_view_basic_sentiment = models.BooleanField(default=True, verbose_name='查看基础情感分析')
    can_view_advanced_sentiment = models.BooleanField(default=False, verbose_name='查看高级情感分析')
    can_export_data = models.BooleanField(default=False, verbose_name='导出数据')
    can_manage_users = models.BooleanField(default=False, verbose_name='用户管理')
    can_system_settings = models.BooleanField(default=False, verbose_name='系统设置')
    
    # 自定义权限
    allowed_platforms = models.TextField(default='', blank=True, verbose_name='允许访问的平台')
    forbidden_features = models.TextField(default='', blank=True, verbose_name='禁止访问的功能')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_permission_profile'
        verbose_name = '用户权限配置'
        verbose_name_plural = '用户权限配置'

    def __str__(self):
        return f"{self.user.username} - {self.get_permission_level_display()}"
    
    @property
    def is_admin(self):
        """判断是否为管理员"""
        return self.permission_level in ['admin', 'super_admin']
    
    @property
    def can_access_platform(self, platform_name):
        """检查是否可以访问特定平台"""
        if self.allowed_platforms == []:
            return True  # 空列表表示可以访问所有平台
        
        return platform_name in self.allowed_platforms
    
    def can_access_feature(self, feature_name):
        """检查是否可以访问特定功能"""
        if feature_name in self.forbidden_features:
            return False
            
        # 基于权限级别的功能访问控制
        feature_permissions = {
            'sentiment_analysis_advanced': self.can_view_advanced_sentiment,
            'export_data': self.can_export_data,
            'manage_users': self.can_manage_users,
            'system_settings': self.can_system_settings,
        }
        
        return feature_permissions.get(feature_name, False)


class FeatureAccessLog(models.Model):
    """功能访问日志表"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    feature_name = models.CharField(max_length=100, verbose_name='功能名称')
    request_path = models.CharField(max_length=500, verbose_name='请求路径')
    ip_address = models.GenericIPAddressField(verbose_name='IP地址')
    user_agent = models.TextField(blank=True, verbose_name='用户代理')
    access_time = models.DateTimeField(auto_now_add=True, verbose_name='访问时间')
    
    class Meta:
        db_table = 'feature_access_log'


class UserProjectPermission(models.Model):
    """用户项目权限表"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    project_poi_id = models.CharField(max_length=255, verbose_name='项目POI ID')
    project_name = models.CharField(max_length=255, verbose_name='项目名称')
    platform = models.CharField(max_length=100, verbose_name='平台')
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                 related_name='granted_permissions', verbose_name='授权人')
    granted_at = models.DateTimeField(auto_now_add=True, verbose_name='授权时间')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    notes = models.TextField(blank=True, null=True, verbose_name='备注')
    
    class Meta:
        db_table = 'user_project_permission'
        unique_together = ['user', 'project_poi_id']
        verbose_name = '用户项目权限'
        verbose_name_plural = '用户项目权限'
    
    def __str__(self):
        return f"{self.user.username} - {self.project_name} ({self.platform})"


class MobileAPIToken(models.Model):
    """手机APP API令牌表"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='用户')
    token = models.CharField(max_length=255, unique=True, verbose_name='API令牌')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    expires_at = models.DateTimeField(verbose_name='过期时间')
    is_active = models.BooleanField(default=True, verbose_name='是否有效')
    last_used = models.DateTimeField(null=True, blank=True, verbose_name='最后使用时间')
    device_info = models.CharField(max_length=500, blank=True, null=True, verbose_name='设备信息')
    
    class Meta:
        db_table = 'mobile_api_token'
        verbose_name = '手机API令牌'
        verbose_name_plural = '手机API令牌'
    
    def __str__(self):
        return f"{self.user.username} - {self.token[:10]}..."
    
    def is_expired(self):
        return timezone.now() > self.expires_at


class SystemPermission(models.Model):
    """系统权限模板表"""
    name = models.CharField(max_length=100, unique=True, verbose_name='权限模板名称')
    description = models.TextField(verbose_name='描述')
    
    # 功能权限
    can_view_basic_sentiment = models.BooleanField(default=True, verbose_name='查看基础情感分析')
    can_view_advanced_sentiment = models.BooleanField(default=False, verbose_name='查看高级情感分析')
    can_export_data = models.BooleanField(default=False, verbose_name='导出数据')
    can_manage_users = models.BooleanField(default=False, verbose_name='用户管理')
    can_system_settings = models.BooleanField(default=False, verbose_name='系统设置')
    
    # 默认平台限制
    default_allowed_platforms = models.TextField(default='', blank=True, verbose_name='默认允许平台')
    
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'system_permission_template'
        verbose_name = '系统权限模板'
        verbose_name_plural = '系统权限模板'
    
    def __str__(self):
        return self.name


# 用户信号处理，自动创建权限配置
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_permission_profile(sender, instance, created, **kwargs):
    """用户创建时自动创建权限配置"""
    if created:
        # 根据用户类型设置默认权限级别
        permission_level = 'analyst' if instance.is_staff else 'basic'
        
        UserPermissionProfile.objects.create(
            user=instance,
            permission_level=permission_level
        )