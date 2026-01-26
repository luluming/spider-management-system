from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_auto_20250929_2039'),
    ]

    operations = [
        migrations.AlterField(
            model_name='operationlog',
            name='action',
            field=models.CharField(
                choices=[
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
                ],
                max_length=50,
                verbose_name='操作类型',
            ),
        ),
    ]


