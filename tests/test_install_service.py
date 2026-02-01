import os
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'install_service.sh'
TEMPLATE = ROOT / 'packaging' / 'systemd' / 'spider-management.service'


def run(args, cwd=None, env=None):
    cmd = ['bash', str(SCRIPT)] + args
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=cwd, env=env, text=True)
    return res.returncode, res.stdout


def test_dry_run_shows_generated_unit(tmp_path):
    # Ensure dry-run works and shows ExecStart replacement
    rc, out = run(['--dry-run', '--uwsgi-path', '/bin/true', '--ini', str(tmp_path / 'uwsgi.ini')])
    assert rc == 0
    assert 'DRY-RUN' in out
    assert 'ExecStart=/bin/true --ini' in out


def test_write_to_non_system_path(tmp_path):
    dest = tmp_path / 'spider-management.service'
    ini = tmp_path / 'uwsgi.ini'
    ini.write_text('[uwsgi]\n')

    rc, out = run(['--dest', str(dest), '--uwsgi-path', '/bin/true', '--ini', str(ini)])
    # Script should succeed writing file even when not root
    assert rc == 0
    assert dest.exists()
    content = dest.read_text()
    assert 'ExecStart=/bin/true --ini' in content
    assert 'User=' in content


def test_missing_ini_fails(tmp_path):
    dest = tmp_path / 'spider-management.service'
    missing_ini = tmp_path / 'missing.ini'

    rc, out = run(['--dest', str(dest), '--uwsgi-path', '/bin/true', '--ini', str(missing_ini)])
    assert rc != 0
    assert '未找到 ini 文件' in out


def test_invalid_ini_requires_force(tmp_path):
    dest = tmp_path / 'spider-management.service'
    ini = tmp_path / 'not_uwsgi.ini'
    ini.write_text('this is not uwsgi config')

    rc, out = run(['--dest', str(dest), '--uwsgi-path', '/bin/true', '--ini', str(ini)])
    assert rc != 0
    assert '可能不是 uwsgi ini 文件' in out

    # With --force it should proceed
    rc2, out2 = run(['--dest', str(dest), '--uwsgi-path', '/bin/true', '--ini', str(ini), '--force'])
    assert rc2 == 0
    assert dest.exists()
    assert '警告' in out2 or '已写入' in out2


def test_module_line_without_section_is_valid(tmp_path):
    dest = tmp_path / 'spider-management.service'
    ini = tmp_path / 'module_no_section.ini'
    ini.write_text('module = myapp:app\n')

    rc, out = run(['--dest', str(dest), '--uwsgi-path', '/bin/true', '--ini', str(ini)])
    assert rc == 0
    assert dest.exists()
    assert 'ExecStart=/bin/true --ini' in dest.read_text()


def test_uwsgi_section_passes(tmp_path):
    dest = tmp_path / 'spider-management.service'
    ini = tmp_path / 'uwsgi_section.ini'
    ini.write_text('[uwsgi]\nmodule = myapp:app\n')

    rc, out = run(['--dest', str(dest), '--uwsgi-path', '/bin/true', '--ini', str(ini)])
    assert rc == 0
    assert dest.exists()
    assert 'ExecStart=/bin/true --ini' in dest.read_text()


if __name__ == '__main__':
    pytest.main([__file__])
