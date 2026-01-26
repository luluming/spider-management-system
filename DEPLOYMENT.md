# 数据管理系统部署指南

## 系统要求

### 硬件要求
- CPU: 2核心以上
- 内存: 4GB以上
- 硬盘: 20GB以上可用空间

### 软件要求
- 操作系统: Linux (CentOS 9.4 推荐)
- Python: 3.9+
- MySQL: 5.7+
- pip: 最新版本

## 安装步骤

### 1. 安装Python和pip
```bash
# CentOS/RHEL
yum install python3 python3-pip -y

# Ubuntu/Debian
apt update
apt install python3 python3-pip -y
```

### 2. 安装MySQL
```bash
# CentOS/RHEL
yum install mysql-server mysql -y
systemctl start mysqld
systemctl enable mysqld

# Ubuntu/Debian
apt install mysql-server mysql-client -y
systemctl start mysql
systemctl enable mysql
```

### 3. 配置MySQL
```bash
# 启动MySQL服务
systemctl start mysqld

# 设置root密码
mysql_secure_installation

# 创建数据库
mysql -u root -p
CREATE DATABASE spider_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON spider_management.* TO 'root'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 4. 安装Python依赖
```bash
pip3 install Django==3.2.24
pip3 install mysqlclient
pip3 install Pillow
pip3 install xlsxwriter
```

### 5. 部署项目
```bash
# 创建项目目录
mkdir -p /opt/spider_management_system
cd /opt/spider_management_system

# 复制项目文件到目录
# (假设项目文件已经在当前目录)
```

### 6. 配置数据库连接
编辑 `spider_management/settings.py` 文件：
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'spider_management',
        'USER': 'root',
        'PASSWORD': 'your_mysql_password',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}
```

### 7. 初始化系统
```bash
# 运行数据库迁移
python3 manage.py migrate

# 创建超级用户
python3 manage.py createsuperuser

# 或运行初始化脚本（包含示例数据）
python3 init_system.py
```

### 8. 启动系统
```bash
# 使用启动脚本
chmod +x start.sh
./start.sh

# 或直接启动
python3 manage.py runserver 0.0.0.0:8000
```

## 生产环境部署

### 1. 使用Nginx + uWSGI

#### 安装uWSGI
```bash
pip3 install uwsgi
```

#### 创建uWSGI配置文件
创建 `uwsgi.ini` 文件：
```ini
[uwsgi]
module = spider_management.wsgi:application
master = true
processes = 4
socket = /opt/spider_management_system/uwsgi.sock
chmod-socket = 666
vacuum = true
die-on-term = true
```

#### 安装Nginx
```bash
# CentOS/RHEL
yum install nginx -y

# Ubuntu/Debian
apt install nginx -y
```

#### 配置Nginx
创建 `/etc/nginx/sites-available/spider_management` 文件：
```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        include uwsgi_params;
        uwsgi_pass unix:/opt/spider_management_system/uwsgi.sock;
    }

    location /static/ {
        alias /opt/spider_management_system/static/;
    }

    location /media/ {
        alias /opt/spider_management_system/media/;
    }
}
```

#### 启用站点
```bash
# Ubuntu/Debian
ln -s /etc/nginx/sites-available/spider_management /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# CentOS/RHEL
cp /etc/nginx/sites-available/spider_management /etc/nginx/conf.d/
nginx -t
systemctl restart nginx
```

### 2. 使用systemd管理服务

创建 `/etc/systemd/system/spider-management.service` 文件：
```ini
[Unit]
Description=Spider Management System
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/opt/spider_management_system
ExecStart=/usr/local/bin/uwsgi --ini uwsgi.ini
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
systemctl daemon-reload
systemctl enable spider-management
systemctl start spider-management
systemctl status spider-management
```

## 系统维护

### 1. 数据备份
```bash
# 备份数据库
mysqldump -u root -p spider_management > backup_$(date +%Y%m%d).sql

# 备份项目文件
tar -czf spider_management_backup_$(date +%Y%m%d).tar.gz /opt/spider_management_system
```

### 2. 日志管理
```bash
# 查看系统日志
journalctl -u spider-management -f

# 查看Nginx日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### 3. 性能监控
```bash
# 查看系统资源使用
top
htop
free -h
df -h

# 查看MySQL状态
mysql -u root -p -e "SHOW PROCESSLIST;"
```

## 故障排除

### 1. 常见问题

#### 数据库连接失败
```bash
# 检查MySQL服务状态
systemctl status mysqld

# 检查端口是否开放
netstat -tlnp | grep 3306

# 检查防火墙
firewall-cmd --list-ports
```

#### 权限问题
```bash
# 检查文件权限
ls -la /opt/spider_management_system/

# 修复权限
chown -R root:root /opt/spider_management_system/
chmod -R 755 /opt/spider_management_system/
```

#### 端口占用
```bash
# 查看端口占用
netstat -tlnp | grep 8000

# 杀死占用进程
kill -9 PID
```

### 2. 日志分析
```bash
# 查看Django错误日志
tail -f /opt/spider_management_system/logs/django.log

# 查看uWSGI日志
tail -f /opt/spider_management_system/logs/uwsgi.log
```

## 安全配置

### 1. 防火墙设置
```bash
# CentOS/RHEL
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=443/tcp
firewall-cmd --reload

# Ubuntu/Debian
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 2. SSL证书配置
```bash
# 使用Let's Encrypt
certbot --nginx -d your_domain.com
```

### 3. 数据库安全
```bash
# 创建专用数据库用户
mysql -u root -p
CREATE USER 'spider_user'@'localhost' IDENTIFIED BY 'strong_password';
GRANT ALL PRIVILEGES ON spider_management.* TO 'spider_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## 更新升级

### 1. 备份当前系统
```bash
# 停止服务
systemctl stop spider-management

# 备份数据库和文件
mysqldump -u root -p spider_management > backup_before_update.sql
tar -czf system_backup_$(date +%Y%m%d).tar.gz /opt/spider_management_system
```

### 2. 更新代码
```bash
# 更新项目文件
# (替换为新版本文件)

# 运行数据库迁移
python3 manage.py migrate

# 收集静态文件
python3 manage.py collectstatic --noinput
```

### 3. 重启服务
```bash
# 启动服务
systemctl start spider-management
systemctl status spider-management
```

---

**部署完成后，系统将在 http://your_domain.com 或 http://your_server_ip:8000 运行**

**默认管理员账号: admin / admin123**


