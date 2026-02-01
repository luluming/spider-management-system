#!/usr/bin/env bash
set -euo pipefail

# 安装 systemd service（支持 dry-run、指定 uwsgi、ini、目标路径与用户创建）
SERVICE_SRC_DEFAULT="$(pwd)/packaging/systemd/spider-management.service"
SERVICE_DST_DEFAULT="/etc/systemd/system/spider-management.service"
DEFAULT_USER="www-data"
DEFAULT_INI="/opt/spider_management_system/uwsgi.ini"

# 参数默认值
SERVICE_SRC="$SERVICE_SRC_DEFAULT"
SERVICE_DST="$SERVICE_DST_DEFAULT"
USER="$DEFAULT_USER"
INI_PATH="$DEFAULT_INI"
UWSGI_PATH=""
DRY_RUN=0
CREATE_USER=0

usage() {
  cat <<EOF
Usage: $0 [--user NAME] [--uwsgi-path PATH] [--ini PATH] [--dest PATH] [--src PATH] [--create-user] [--dry-run]

Options:
  --user NAME         Set the User in the unit (default: ${DEFAULT_USER})
  --uwsgi-path PATH   Absolute path to uwsgi executable (if omitted, will try to find in PATH)
  --ini PATH          Path to uwsgi ini file (default: ${DEFAULT_INI})
  --dest PATH         Destination systemd unit path (default: ${SERVICE_DST_DEFAULT})
  --src PATH          Source unit template (default: packaging/systemd/spider-management.service)
  --create-user       Create system user if it does not exist
  --dry-run           Show actions without performing them
  --help              Show this help
EOF
}

# 早期分支：当脚本被自调用用于内嵌的 Python ini 校验时直接执行校验并退出
if [ "${1:-}" = "__python_ini_check_placeholder__" ]; then
  INI_TO_CHECK="$2"
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY' "$INI_TO_CHECK"
import sys, configparser
fn = sys.argv[1]
cfg = configparser.ConfigParser()
try:
    with open(fn) as f:
        cfg.read_file(f)
except Exception:
    sys.exit(2)
if cfg.has_section('uwsgi'):
    sys.exit(0)
for s in cfg.sections():
    for key in ('module', 'socket', 'mount', 'callable', 'vacuum', 'chdir'):
        if cfg.has_option(s, key):
            sys.exit(0)
sys.exit(2)
PY
    exit $?
  else
    exit 1
  fi
fi

# 参数解析
FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --user)
      USER="$2"; shift 2;;
    --uwsgi-path)
      UWSGI_PATH="$2"; shift 2;;
    --ini)
      INI_PATH="$2"; shift 2;;
    --dest|--dst)
      SERVICE_DST="$2"; shift 2;;
    --src)
      SERVICE_SRC="$2"; shift 2;;
    --create-user)
      CREATE_USER=1; shift;;
    --dry-run)
      DRY_RUN=1; shift;;
    --force)
      FORCE=1; shift;;
    --help)
      usage; exit 0;;
    *)
      echo "Unknown option: $1"; usage; exit 1;;
  esac
done

# 检查 source
if [ ! -f "$SERVICE_SRC" ]; then
  echo "找不到 $SERVICE_SRC，请确保在项目根目录运行或指定 --src。"
  exit 2
fi

# 检查 uwsgi
if [ -n "$UWSGI_PATH" ]; then
  if [ ! -x "$UWSGI_PATH" ]; then
    echo "指定的 uwsgi 不可执行：$UWSGI_PATH"; exit 3
  fi
else
  if command -v uwsgi >/dev/null 2>&1; then
    UWSGI_PATH="$(command -v uwsgi)"
  else
    # 尝试在常见虚拟环境位置查找
    if [ -x "./venv/bin/uwsgi" ]; then
      UWSGI_PATH="$(pwd)/venv/bin/uwsgi"
    fi
  fi
fi

if [ -z "$UWSGI_PATH" ]; then
  echo "警告：未找到 uwsgi 可执行文件。请通过 --uwsgi-path 指定虚拟环境中的 uwsgi。"
fi

# 检查 ini 文件是否存在且看起来像 uwsgi ini
if [ ! -f "$INI_PATH" ]; then
  echo "错误：未找到 ini 文件 $INI_PATH。请指定有效的 --ini 路径。"
  exit 5
fi

# 增强校验：优先使用 python3 的 configparser 解析，如果不可用或解析失败则回退到文本检查
ini_ok=0
if command -v python3 >/dev/null 2>&1; then
  # 通过向脚本自调用的方式触发内嵌的 python 检查（避免重复将 heredoc 放到多个位置）
  if bash "$0" "__python_ini_check_placeholder__" "$INI_PATH" >/dev/null 2>&1; then
    ini_ok=1
  else
    echo "警告：使用 Python 解析 $INI_PATH 未通过（将尝试回退到文本检查）。"
  fi
fi

if [ "$ini_ok" -eq 0 ]; then
  if grep -E -q '^\[uwsgi\]|^\s*module=|^\s*socket=|uwsgi' "$INI_PATH"; then
    ini_ok=1
  fi
fi

if [ "$ini_ok" -eq 0 ]; then
  if [ "$FORCE" -eq 1 ]; then
    echo "警告：$INI_PATH 看起来不是有效的 uwsgi ini（未发现 [uwsgi]、module 或 socket）。使用 --force 强制继续。"
  else
    echo "错误：$INI_PATH 可能不是 uwsgi ini 文件（未发现 [uwsgi]、module 或 socket）。如确定继续请使用 --force。"
    exit 6
  fi
fi

# 生成 ExecStart
if [ -n "$UWSGI_PATH" ]; then
  EXEC_START="$UWSGI_PATH --ini $INI_PATH"
else
  EXEC_START="/usr/bin/env uwsgi --ini $INI_PATH"
fi

# Python 解析实现（放在此处以便能够被上面的 heredoc 调用）
# 仅当直接以 python3 heredoc 调用时执行下面的逻辑
if [ "${1:-}" = "__python_ini_check_placeholder__" ]; then
  python3 - <<'PY'
import sys, configparser
fn = sys.argv[1]
cfg = configparser.ConfigParser()
try:
    with open(fn) as f:
        # configparser requires sections; if file lacks sections, treat as not parsed
        cfg.read_file(f)
except Exception:
    sys.exit(2)
# 如果包含 [uwsgi] 节直接认为通过
if cfg.has_section('uwsgi'):
    sys.exit(0)
# 否则检查是否有关键字段
for s in cfg.sections():
    for key in ('module', 'socket', 'mount', 'callable', 'vacuum', 'chdir'):
        if cfg.has_option(s, key):
            sys.exit(0)
# 若没有找到，则视为失败
sys.exit(2)
PY
fi

# 检查权限（如果要写入 /etc 需要 root）
need_root=0
case "$SERVICE_DST" in
  /etc/*|/lib/systemd/*)
    need_root=1;;
esac
if [ "$need_root" -eq 1 ] && [ "$(id -u)" -ne 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  echo "错误：目标路径 $SERVICE_DST 需要 root 权限。使用 sudo 运行或指定非 /etc 路径。"; exit 4
fi

# 可选创建用户
if [ "$CREATE_USER" -eq 1 ] && [ "$(id -u)" -eq 0 ]; then
  if id -u "$USER" >/dev/null 2>&1; then
    echo "用户 $USER 已存在，跳过创建。"
  else
    echo "创建系统用户 $USER ..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$USER"
  fi
fi

# 备份已存在的 service
if [ -f "$SERVICE_DST" ]; then
  ts="$(date +%s)"
  echo "备份现有 unit: $SERVICE_DST -> ${SERVICE_DST}.bak.$ts"
  if [ "$DRY_RUN" -eq 0 ]; then
    cp "$SERVICE_DST" "${SERVICE_DST}.bak.$ts"
  fi
fi

# 生成临时 unit 并替换占位符
tmpfile="$(mktemp)"
trap 'rm -f "$tmpfile"' EXIT
sed "s|{{EXEC_START}}|${EXEC_START}|g" "$SERVICE_SRC" > "$tmpfile"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "DRY-RUN: 将把模板 $SERVICE_SRC 用替换后的 ExecStart 写入 $SERVICE_DST。"
  echo "--- BEGIN GENERATED UNIT ---"
  sed -n '1,200p' "$tmpfile"
  echo "--- END GENERATED UNIT ---"
  exit 0
fi

# 写入目标
mkdir -p "$(dirname "$SERVICE_DST")"
cp "$tmpfile" "$SERVICE_DST"
chmod 644 "$SERVICE_DST"

# 修改 unit 中的 User 字段（简单替换）
# 注意：此替换假设模板中已有 User= 行
sed -i "s/^User=.*/User=${USER}/" "$SERVICE_DST"

# 重新加载 systemd 并 enable/start（仅在写入系统路径时）
if [ "$need_root" -eq 1 ]; then
  systemctl daemon-reload
  systemctl enable --now spider-management
  systemctl status spider-management --no-pager || true
else
  echo "已写入 $SERVICE_DST（非系统路径，不会触发 systemctl 操作）。"
fi

echo "spider-management unit 已生成并写入：$SERVICE_DST"