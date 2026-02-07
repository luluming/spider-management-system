#!/bin/bash
# 设置评论数据时间异常自动修复定时任务（每天凌晨2点执行）
# 使用方法: sudo bash scripts/setup_auto_fix_cron.sh

PROJECT_DIR="/opt/spider_management_system"
PYTHON="${PYTHON:-python3}"
CRON_ENTRY="0 2 * * * cd $PROJECT_DIR && $PYTHON manage.py auto_fix_comment_anomalies >> /var/log/auto_fix_comment_anomalies.log 2>&1"

# 检查是否已存在
if crontab -l 2>/dev/null | grep -q "auto_fix_comment_anomalies"; then
    echo "定时任务已存在"
else
    (crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
    echo "已添加定时任务: 每天凌晨2点执行 auto_fix_comment_anomalies"
fi
