try:
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "未找到 PyMySQL。请在「当前已激活的虚拟环境」里安装依赖：\n"
        "  cd /Users/fangyi/Desktop/Django/daily_report_site\n"
        "  source .venv/bin/activate          # 若使用项目自带 venv\n"
        "  pip install -r requirements.txt\n"
        "若你用的是别的目录下的 .venv（例如 ~/Desktop/Django/.venv），"
        "也要在那个环境里执行：pip install PyMySQL"
    ) from exc
