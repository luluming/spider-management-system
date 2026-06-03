# Generated manually for App collector mobile API models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('spiders', '0005_add_spiderbase_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AppCollector',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=150, unique=True, verbose_name='登录账号')),
                ('password', models.CharField(max_length=128, verbose_name='密码哈希')),
                ('display_name', models.CharField(blank=True, default='', max_length=150, verbose_name='显示名')),
                ('phone', models.CharField(blank=True, default='', max_length=20, verbose_name='手机号')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('failed_login_count', models.PositiveIntegerField(default=0, verbose_name='连续登录失败次数')),
                ('locked_until', models.DateTimeField(blank=True, null=True, verbose_name='锁定截止时间')),
                ('last_login_at', models.DateTimeField(blank=True, null=True, verbose_name='最近登录时间')),
                ('last_login_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='最近登录IP')),
                ('bound_device_id', models.CharField(blank=True, default='', max_length=255, verbose_name='绑定设备ID')),
                ('bound_device_info', models.CharField(blank=True, default='', max_length=500, verbose_name='绑定设备信息')),
                ('device_bound_at', models.DateTimeField(blank=True, null=True, verbose_name='设备绑定时间')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_collectors', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
            ],
            options={
                'verbose_name': 'App采集员',
                'verbose_name_plural': 'App采集员',
                'db_table': 'app_collector',
            },
        ),
        migrations.CreateModel(
            name='AppProjectPermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('poi_id', models.CharField(max_length=255, verbose_name='POI ID')),
                ('item_name', models.CharField(max_length=255, verbose_name='项目名称')),
                ('platform', models.CharField(max_length=100, verbose_name='平台')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否有效')),
                ('granted_at', models.DateTimeField(auto_now_add=True, verbose_name='授权时间')),
                ('notes', models.TextField(blank=True, default='', verbose_name='备注')),
                ('collector', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_permissions', to='spiders.appcollector')),
                ('granted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='granted_app_permissions', to=settings.AUTH_USER_MODEL, verbose_name='授权人')),
            ],
            options={
                'verbose_name': 'App项目权限',
                'verbose_name_plural': 'App项目权限',
                'db_table': 'app_project_permission',
                'unique_together': {('collector', 'poi_id')},
            },
        ),
        migrations.CreateModel(
            name='AppAPIToken',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=255, unique=True)),
                ('device_id', models.CharField(blank=True, default='', max_length=255)),
                ('expires_at', models.DateTimeField()),
                ('is_active', models.BooleanField(default=True)),
                ('last_used', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('collector', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='api_tokens', to='spiders.appcollector')),
            ],
            options={
                'verbose_name': 'App API Token',
                'verbose_name_plural': 'App API Tokens',
                'db_table': 'app_api_token',
            },
        ),
        migrations.CreateModel(
            name='AppCommentSubmission',
            fields=[
                ('comment_id', models.CharField(max_length=32, primary_key=True, serialize=False)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('collector', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comment_submissions', to='spiders.appcollector')),
            ],
            options={
                'verbose_name': 'App评论上报记录',
                'verbose_name_plural': 'App评论上报记录',
                'db_table': 'app_comment_submission',
            },
        ),
        migrations.CreateModel(
            name='AppDeviceRebindRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_no', models.CharField(max_length=32, unique=True)),
                ('old_device_id', models.CharField(blank=True, default='', max_length=255)),
                ('new_device_id', models.CharField(max_length=255)),
                ('new_device_info', models.CharField(blank=True, default='', max_length=500)),
                ('verify_code_hash', models.CharField(max_length=128)),
                ('verify_code_expires_at', models.DateTimeField()),
                ('verify_attempts', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(choices=[('pending_old_verify', '待旧设备验证'), ('pending_admin', '待管理员审批'), ('approved', '已批准'), ('completed', '已完成'), ('rejected', '已拒绝'), ('expired', '已过期'), ('cancelled', '已取消')], default='pending_old_verify', max_length=32)),
                ('old_verified_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reject_reason', models.TextField(blank=True, default='')),
                ('approved_expires_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('request_ip', models.GenericIPAddressField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('collector', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rebind_requests', to='spiders.appcollector')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_rebind_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'App设备换绑申请',
                'verbose_name_plural': 'App设备换绑申请',
                'db_table': 'app_device_rebind_request',
            },
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='qusetanswer',
                    name='comment_id',
                    field=models.CharField(max_length=500, primary_key=True, serialize=False),
                ),
                migrations.AlterField(
                    model_name='qusetanswer',
                    name='comment_grade',
                    field=models.CharField(blank=True, default='0', max_length=255),
                ),
                migrations.AddField(
                    model_name='qusetanswer',
                    name='c_num',
                    field=models.IntegerField(default=0),
                ),
                migrations.AddField(
                    model_name='qusetanswer',
                    name='create_time',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='qusetanswer',
                    name='reply_content',
                    field=models.TextField(blank=True, default=''),
                ),
                migrations.AddField(
                    model_name='qusetanswer',
                    name='reply_img',
                    field=models.IntegerField(default=0),
                ),
                migrations.AddField(
                    model_name='qusetanswer',
                    name='reply_video',
                    field=models.PositiveIntegerField(default=0),
                ),
                migrations.AlterField(
                    model_name='qusetanswer',
                    name='comment_num',
                    field=models.FloatField(default=0.0),
                ),
                migrations.AlterField(
                    model_name='qusetanswer',
                    name='user_id',
                    field=models.CharField(blank=True, default='', max_length=255),
                ),
            ],
            database_operations=[],
        ),
    ]
