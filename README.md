# 数据管理系统

## 项目概述

数据管理系统是一个完整的旅游平台评论数据管理系统，用于管理、分析和展示从多个旅游平台采集的评论数据。系统提供数据查询、筛选、统计分析、用户管理等功能。

## 技术架构

- **后端框架**: Django 3.2.24
- **数据库**: MySQL 5.7+
- **前端技术**: HTML5, CSS3, JavaScript, Bootstrap 5
- **数据可视化**: Chart.js
- **AJAX**: 异步数据交互
- **Python版本**: 3.9+

## 功能特性

### 1. 用户认证与权限管理
- 用户登录/登出
- 验证码验证
- 密码修改
- 基于角色的权限控制（普通用户/管理员）

### 2. 评论数据管理
- 多维度数据筛选（平台、项目、时间、评分、关键词）
- 智能平台与项目联动筛选
- 分页显示和页面大小调整
- AJAX无刷新操作

### 3. 数据统计分析
- 关键指标概览（总评论数、平均评分、点赞数、回复数、活跃用户）
- 数据可视化图表（评分分布饼图、活跃用户柱状图）
- 实时统计数据更新

### 4. 数据导出
- 支持Excel/CSV格式导出
- 导出数据包含所有筛选条件

### 5. 系统管理（管理员功能）
- 用户管理（创建、编辑、删除、状态管理）
- 操作日志查看
- 完整的操作审计

## 安装部署

### 1. 环境要求
- Python 3.9+
- MySQL 5.7+
- pip包管理器

### 2. 安装依赖
```bash
pip install Django==3.2.24
pip install mysqlclient
pip install Pillow
pip install xlsxwriter
```

### 3. 数据库配置
1. 启动MySQL服务：
```bash
systemctl start mysqld
```

2. 创建数据库：
```sql
CREATE DATABASE spider_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

3. 修改数据库配置（`spider_management/settings.py`）：
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'spider_management',
        'USER': 'root',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}
```

### 4. 初始化系统
```bash
# 运行数据库迁移
python manage.py migrate

# 创建超级用户
python manage.py createsuperuser

# 或者运行初始化脚本（包含示例数据）
python init_system.py
```

### 5. 启动系统
```bash
# 使用启动脚本
./start.sh

# 或直接启动
python manage.py runserver 0.0.0.0:8000
```

## 使用说明

### 1. 登录系统
- 访问：http://localhost:8000/accounts/login/
- 默认管理员账号：admin / admin123
- 支持验证码验证

### 2. 主要功能

#### 仪表板
- 查看系统整体统计数据
- 今日数据概览
- 评分分布和活跃用户图表
- 平台数据统计

#### 评论数据
- 多维度筛选：平台、项目、时间范围、评分、关键词
- 智能联动：选择平台后自动加载对应项目列表
- 分页浏览：支持10/20/50/100条每页
- 排序功能：按时间、评分、点赞数、回复数排序
- 数据导出：支持Excel和CSV格式

#### 用户管理（管理员）
- 用户列表查看
- 添加新用户
- 编辑用户信息
- 删除用户
- 用户状态管理

#### 操作日志（管理员）
- 查看所有用户操作记录
- 按操作类型筛选
- 查看IP地址和操作时间

### 3. 数据模型

#### 核心数据表
- `quset_answer`: 评论数据主表
- `spider_base`: 爬虫基础数据表
- `p_sentiment`: 情感分析数据表
- `user_profile`: 用户扩展信息表
- `operation_log`: 操作日志表

## 系统配置

### 1. 时区设置
系统默认使用中国时区（Asia/Shanghai），可在`settings.py`中修改：
```python
TIME_ZONE = 'Asia/Shanghai'
```

### 2. 语言设置
系统默认使用中文，可在`settings.py`中修改：
```python
LANGUAGE_CODE = 'zh-hans'
```

### 3. 静态文件
静态文件目录：`/static/`
媒体文件目录：`/media/`

## 开发说明

### 1. 项目结构
```
spider_management_system/
├── accounts/                 # 用户认证应用
│   ├── models.py            # 用户和操作日志模型
│   ├── views.py             # 认证相关视图
│   ├── urls.py              # 认证URL配置
│   └── admin.py             # 管理后台配置
├── spiders/                  # 爬虫数据应用
│   ├── models.py            # 数据模型
│   ├── views.py             # 数据管理视图
│   ├── urls.py              # 数据URL配置
│   └── admin.py             # 管理后台配置
├── templates/                # 模板文件
│   ├── base.html            # 基础模板
│   ├── accounts/             # 认证相关模板
│   └── spiders/              # 数据管理模板
├── static/                   # 静态文件
├── spider_management/        # 项目配置
│   ├── settings.py           # 项目设置
│   ├── urls.py               # 主URL配置
│   └── wsgi.py               # WSGI配置
├── manage.py                 # Django管理脚本
├── init_system.py            # 系统初始化脚本
└── start.sh                  # 启动脚本
```

### 2. 添加新功能
1. 在相应应用中添加模型
2. 创建视图函数
3. 配置URL路由
4. 创建模板文件
5. 运行数据库迁移

### 3. 自定义样式
系统使用Bootstrap 5框架，可在模板中自定义CSS样式。

## 故障排除

### 1. 数据库连接问题
- 检查MySQL服务是否启动：`systemctl status mysqld`
- 检查数据库配置是否正确
- 确认数据库用户权限

### 2. 静态文件问题
- 运行：`python manage.py collectstatic`
- 检查静态文件路径配置

### 3. 权限问题
- 检查文件权限：`chmod +x start.sh`
- 检查目录权限：`chmod -R 755 /opt/spider_management_system`

## 更新日志

### v1.0.0 (2025-01-27)
- 初始版本发布
- 实现基础用户认证功能
- 实现评论数据管理功能
- 实现数据统计和可视化
- 实现用户管理和操作日志
- 支持数据导出功能

## 技术支持

如有问题或建议，请联系开发团队。

---

**开发团队**: stone  
**最后更新**: 2025年1月27日  
**版本**: v1.0.0


