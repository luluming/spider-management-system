# Generated manually for user management models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('spiders', '0003_auto_20250929_1359'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProjectPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('project_poi_id', models.CharField(max_length=255, verbose_name='项目POI ID')),
                ('project_name', models.CharField(max_length=255, verbose_name='项目名称')),
                ('platform', models.CharField(max_length=100, verbose_name='平台')),
                ('granted_at', models.DateTimeField(auto_now_add=True, verbose_name='授权时间')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否有效')),
                ('notes', models.TextField(blank=True, null=True, verbose_name='备注')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户')),
                ('granted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='granted_permissions', to=settings.AUTH_USER_MODEL, verbose_name='授权人')),
            ],
            options={
                'verbose_name': '用户项目权限',
                'verbose_name_plural': '用户项目权限',
                'db_table': 'user_project_permission',
                'unique_together': {('user', 'project_poi_id')},
            },
        ),
        migrations.CreateModel(
            name='MobileAPIToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=255, unique=True, verbose_name='API令牌')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('expires_at', models.DateTimeField(verbose_name='过期时间')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否有效')),
                ('last_used', models.DateTimeField(blank=True, null=True, verbose_name='最后使用时间')),
                ('device_info', models.CharField(blank=True, max_length=500, null=True, verbose_name='设备信息')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '手机API令牌',
                'verbose_name_plural': '手机API令牌',
                'db_table': 'mobile_api_token',
            },
        ),
    ]
