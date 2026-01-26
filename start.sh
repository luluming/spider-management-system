#!/bin/bash
# 爬虫管理系统启动脚本
# Author: stone

echo "=========================================="
echo "爬虫管理系统启动脚本"
echo "=========================================="

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: Python3 未安装"
    exit 1
fi

# 检查Django是否安装
if ! python3 -c "import django" &> /dev/null; then
    echo "错误: Django 未安装"
    exit 1
fi

# 进入项目目录
cd /opt/spider_management_system

# 检查数据库连接
echo "检查数据库连接..."
python3 manage.py check --database default
if [ $? -ne 0 ]; then
    echo "数据库连接失败，请检查MySQL服务是否启动"
    echo "启动MySQL服务: systemctl start mysqld"
    exit 1
fi

# 运行数据库迁移
echo "运行数据库迁移..."
python3 manage.py migrate

# 收集静态文件
echo "收集静态文件..."
python3 manage.py collectstatic --noinput

# 启动Django开发服务器
echo "启动Django服务器..."
echo "系统将在 http://localhost:8000 启动"
echo "按 Ctrl+C 停止服务器"
echo "=========================================="

python3 manage.py runserver 0.0.0.0:8000


