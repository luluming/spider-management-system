from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='QusetAnswer',
            fields=[
                ('comment_id', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('poiId', models.CharField(max_length=255, db_column='poiId')),
                ('user_name', models.CharField(max_length=255, blank=True)),
                ('comment_content', models.TextField(blank=True)),
                ('comment_grade', models.FloatField(default=0.0)),
                ('like_num', models.IntegerField(default=0)),
                ('reply_num', models.IntegerField(default=0)),
                ('release_time', models.DateTimeField()),
                ('user_id', models.CharField(max_length=255, blank=True)),
                ('comment_num', models.IntegerField(default=0)),
            ],
            options={
                'db_table': 'quset_answer',
            },
        ),
        migrations.CreateModel(
            name='PSentiment',
            fields=[
                ('poiId', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('source_c', models.CharField(max_length=100, blank=True)),
                ('source_type', models.CharField(max_length=100, blank=True)),
                ('title', models.CharField(max_length=255, blank=True)),
                ('url', models.CharField(max_length=500, blank=True)),
                ('p_time', models.DateTimeField()),
                ('comment_num', models.CharField(max_length=20, default='0.0', blank=True)),
                ('reply_num', models.IntegerField(default=0)),
                ('user_id', models.CharField(max_length=255, blank=True)),
                ('y_name', models.CharField(max_length=255, blank=True)),
                ('y_num', models.CharField(max_length=255, blank=True)),
                ('itemName', models.CharField(max_length=255, blank=True, db_column='itemName')),
            ],
            options={
                'db_table': 'p_sentiment',
            },
        ),
        migrations.CreateModel(
            name='SpiderBase',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('SalesChannel', models.CharField(max_length=255, null=True, blank=True, db_column='SalesChannel')),
                ('industry', models.CharField(max_length=255, null=True, blank=True)),
                ('request_data', models.TextField(null=True, blank=True, db_column='request_data')),
                ('project_id', models.CharField(max_length=100, null=True, blank=True)),
                ('IteamName', models.CharField(max_length=255, null=True, blank=True, db_column='IteamName')),
                ('IteamState', models.CharField(max_length=255, null=True, blank=True)),
                ('poid', models.BigIntegerField(null=True, blank=True, db_column='poid')),
                ('sort_type', models.CharField(max_length=10, null=True, blank=True)),
                ('total_collection_page', models.IntegerField(null=True, blank=True)),
                ('city', models.CharField(max_length=255, null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True, blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True, null=True, blank=True)),
                ('created_by', models.ForeignKey(null=True, blank=True, on_delete=models.deletion.SET_NULL, to='auth.user', db_column='created_by_id')),
            ],
            options={
                'db_table': 'spider_base',
            },
        ),
        migrations.CreateModel(
            name='UserPermissionProfile',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('permission_level', models.CharField(max_length=20, default='basic')),
                ('can_view_basic_sentiment', models.BooleanField(default=True)),
                ('can_view_advanced_sentiment', models.BooleanField(default=False)),
                ('can_export_data', models.BooleanField(default=False)),
                ('can_manage_users', models.BooleanField(default=False)),
                ('can_system_settings', models.BooleanField(default=False)),
                ('allowed_platforms', models.TextField(blank=True, default='')),
                ('forbidden_features', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, to='auth.user', related_name='permission_profile')),
            ],
            options={
                'db_table': 'user_permission_profile',
                'verbose_name': '用户权限配置',
                'verbose_name_plural': '用户权限配置',
            },
        ),
        migrations.CreateModel(
            name='FeatureAccessLog',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('feature_name', models.CharField(max_length=100)),
                ('request_path', models.CharField(max_length=500)),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField(blank=True)),
                ('access_time', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'db_table': 'feature_access_log',
            },
        ),
        migrations.CreateModel(
            name='UserProjectPermission',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('project_poi_id', models.CharField(max_length=255)),
                ('project_name', models.CharField(max_length=255)),
                ('platform', models.CharField(max_length=100)),
                ('granted_at', models.DateTimeField(auto_now_add=True)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, to='auth.user')),
                ('granted_by', models.ForeignKey(null=True, blank=True, on_delete=models.deletion.SET_NULL, related_name='granted_permissions', to='auth.user')),
            ],
            options={
                'db_table': 'user_project_permission',
                'unique_together': {('user', 'project_poi_id')},
            },
        ),
        migrations.CreateModel(
            name='MobileAPIToken',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('token', models.CharField(max_length=255, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('is_active', models.BooleanField(default=True)),
                ('last_used', models.DateTimeField(blank=True, null=True)),
                ('device_info', models.CharField(blank=True, max_length=500, null=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, to='auth.user')),
            ],
            options={
                'db_table': 'mobile_api_token',
            },
        ),
        migrations.CreateModel(
            name='SystemPermission',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('description', models.TextField()),
                ('can_view_basic_sentiment', models.BooleanField(default=True)),
                ('can_view_advanced_sentiment', models.BooleanField(default=False)),
                ('can_export_data', models.BooleanField(default=False)),
                ('can_manage_users', models.BooleanField(default=False)),
                ('can_system_settings', models.BooleanField(default=False)),
                ('default_allowed_platforms', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'system_permission_template',
            },
        ),
    ]

