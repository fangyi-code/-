# Django 日报系统（Daily Brief）

每日 RSS 聚合 + Open-Meteo 天气 + 火山方舟（豆包）结构化分析；飞书式目录 + 气泡概览 + 底部 Tab；支持注册登录与新闻卡片评论、LLM 辅助搜索。

## 合规与费用说明

- **新闻**：仅通过 **RSS/Atom** 拉取各源在订阅中提供的内容，适合课堂/简历说明；未做商业站点整站 HTML 高频抓取。
- **天气**：[Open-Meteo](https://open-meteo.com/)，**无需 API Key**。
- **今日首页天气**：与生成日报时写入库里的「天气与环境」块可以不同——**今日**页按 **个人设置中的城市/坐标（优先）→ 公网 IP 粗定位（ip-api.com）→ `DEFAULT_CITY_NAME`** 实时拉取展示；**历史某日**页仍显示生成当日保存的天气正文。本机 `127.0.0.1` 等私网 IP 不会走 IP 定位，会落到默认城市。若部署在 Nginx 等反向代理后，需在 `.env` 设置 `TRUST_X_FORWARDED_FOR=True`，以便用 `X-Forwarded-For` 取真实客户端 IP。
- **大模型**：火山引擎 [方舟](https://www.volcengine.com/product/ark) 豆包，一般有试用额度；请在控制台查看计费与额度。

## 环境要求

- Python 3.10+
- MySQL 5.7+ / 8.x（数据库字符集建议 `utf8mb4`）

## 快速开始

```bash
cd daily_report_site
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`（**不要**把真实密码提交到 Git）：

- `SECRET_KEY`：随机字符串
- `MYSQL_*`：你的 MySQL 连接信息
- `ARK_API_KEY`、`ARK_MODEL`：方舟 API Key 与推理接入点 ID（可选；不填则生成报告时走降级文案）

```bash
python manage.py migrate
python manage.py seed_feedsources
python manage.py generate_daily_report
python manage.py runserver
```

浏览器访问 <http://127.0.0.1:8000/>。管理员：`python manage.py createsuperuser` 后访问 `/admin/`。

### 新闻源（中文 RSS）与重新生成日报

- 默认种子为 **中文 RSS**（新华网、人民网、中新网、36氪、少数派、爱范儿、异次元等）。若你曾在旧版本入库过 BBC、卫报等英文源，可执行  
  `python manage.py seed_feedsources --disable-known-en-feeds`  
  将这两类 URL **停用**；也可在 `/admin/` 里编辑 `FeedSource` 自行增删、勾选「启用」。
- 修改订阅源或启用状态后，需要 **重新生成当日内容** 才会反映到首页：  
  `python manage.py generate_daily_report`
- 新装中文默认项（表已有数据时）：`python manage.py seed_feedsources --force`

### 常见问题：`ModuleNotFoundError: No module named 'pymysql'`

说明 **当前终端里激活的虚拟环境** 里没有安装依赖。报错里若出现 `/某路径/Django/.venv/`，说明你用的是「上一级文件夹」的 venv，而不是 `daily_report_site/.venv`。

**做法二选一：**

1. **用项目自带环境（推荐）**

```bash
cd /Users/fangyi/Desktop/Django/daily_report_site
source .venv/bin/activate
pip install -r requirements.txt
```

2. **坚持用你现在的 venv**（例如已 `source ../.venv/bin/activate`）：在同一终端执行

```bash
pip install -r /Users/fangyi/Desktop/Django/daily_report_site/requirements.txt
```

然后用 `which python` 确认 `python` 指向你期望的 `.venv`。

**注意**：四条命令请 **分开执行**；若第一条 `migrate` 失败，后面也会连锁报错，先解决依赖再重新跑。

### 常见问题：`cryptography package is required for caching_sha2_password`

MySQL 8 默认用户认证插件是 `caching_sha2_password`，PyMySQL 需要 **cryptography** 才能连接。在项目 venv 中执行：

```bash
pip install cryptography
```

或直接 `pip install -r requirements.txt`（`requirements.txt` 已包含该依赖）。

**备选**（改服务器端，一般不必）：在 MySQL 里把该用户改成 `mysql_native_password`（需有数据库管理权限）。

## 每日 6:00 自动跑报

在 **macOS** 可用 `launchd`（将路径与用户名改成你的环境）：

1. 新建 `~/Library/LaunchAgents/com.dailyreport.generate.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.dailyreport.generate</string>
  <key>WorkingDirectory</key>
  <string>/Users/你的用户名/Desktop/Django/daily_report_site</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/你的用户名/Desktop/Django/daily_report_site/.venv/bin/python</string>
    <string>manage.py</string>
    <string>generate_daily_report</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>/tmp/daily_report_cron.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/daily_report_cron.err</string>
</dict>
</plist>
```

2. 加载任务：

```bash
launchctl load ~/Library/LaunchAgents/com.dailyreport.generate.plist
```

**Linux** 可使用 `crontab -e`：

```cron
0 6 * * * cd /path/to/daily_report_site && .venv/bin/python manage.py generate_daily_report >> /tmp/daily_report.log 2>&1
```

说明：任务使用服务器**本地时间**；本项目 `TIME_ZONE` 为 `Asia/Shanghai`，与 Cron 机器时区一致即可。

## 项目结构（摘要）

- `config/`：Django 配置（MySQL、静态文件、方舟环境变量）
- `reports/`：模型、视图、模板、RSS/天气/LLM 服务、`generate_daily_report` 管理命令
- `templates/`、`static/`：页面与样式（浅色 + 橙色渐变 + 明暗切换）

## 依赖说明

- 使用 **PyMySQL** 作为 MySQL 驱动（免系统 `mysqlclient` 编译依赖）；生产环境也可改用 `mysqlclient` 并去掉 `config/__init__.py` 中的 `pymysql.install_as_MySQLdb()`。
