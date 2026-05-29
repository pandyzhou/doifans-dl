# doifans-dl

Paywall bypass video downloader for [doifans.vip](https://doifans.vip).

Downloads any creator's paid/locked videos without a valid subscription.

---

**[中文说明](#中文说明)** | **[English](#english)**

---

## 中文说明

### 这是什么

doifans.vip 是一个基于 Sponzy v4.6 搭建的 OnlyFans 克隆盗版站. 本工具利用其多个安全漏洞, 实现无需付费即可下载任意创作者的全部视频.

### 环境要求

- Python 3.10+
- 网络代理 (站点使用 Cloudflare, 大陆直连可能不通)
- 无需注册账号 (工具内置凭据)

### 安装

```bash
# 方式一: pip 安装 (推荐)
pip install git+https://github.com/Sophomoresty/doifans-dl.git

# 方式二: 克隆后安装
git clone https://github.com/Sophomoresty/doifans-dl.git
cd doifans-dl
pip install .
```

### 使用

```bash
# 下载某个创作者的全部视频
doifans-dl --proxy http://127.0.0.1:7890 ouyangqin

# 只列出视频链接 (不下载)
doifans-dl --proxy http://127.0.0.1:7890 hongkongdoll --list

# 指定输出目录
doifans-dl --proxy http://127.0.0.1:7890 wantingwan -o ~/Videos

# 检查连通性
doifans-dl --proxy http://127.0.0.1:7890 doctor

# 不用代理 (如果你的网络能直连)
doifans-dl ouyangqin
```

`--proxy` 支持 HTTP 和 SOCKS5 代理, 格式: `http://IP:PORT` 或 `socks5://IP:PORT`

### 输出

默认下载到 `./downloads/<creator>/` 目录, 每个视频一个 .mp4 文件. 已存在的文件会自动跳过.

加 `--list` 输出 JSON 格式的视频 URL 列表, 可配合 aria2/IDM 等工具批量下载.

### 已测试创作者

| 创作者 | 视频数 | 总大小 |
|--------|--------|--------|
| ouyangqin | 23 | ~2.2 GB |
| hongkongdoll | 20 | ~8 GB |
| wantingwan | 123 | ~50 GB |

### 原理

```
伪造 Stripe Webhook → 钱包充值 → 购买订阅 → 抓取视频 URL → 直接下载
```

1. `/stripe/webhook` 无签名验证, 伪造 `checkout.session.completed` 事件给钱包充值
2. 用 JSON Content-Type 绕过 WAF 登录限制
3. 用钱包余额购买任意创作者的月度订阅
4. 从创作者主页和 AJAX 分页接口抓取所有视频 URL
5. nginx 对视频静态文件无鉴权, 直接 GET 下载

### 注意事项

- 站点随时可能修复漏洞或下线, 工具可能失效
- 视频文件较大, 确保磁盘空间充足
- 代理需要稳定, 大文件下载中断需重新运行 (已下载的会跳过)

---

## English

### What is this

doifans.vip is a pirated OnlyFans clone built on Sponzy v4.6. This tool exploits multiple security vulnerabilities to download any creator's paid videos without payment.

### Requirements

- Python 3.10+
- Network proxy (site is behind Cloudflare, may be inaccessible from some regions)
- No account registration needed (credentials are built-in)

### Install

```bash
# Option 1: pip from GitHub (recommended)
pip install git+https://github.com/Sophomoresty/doifans-dl.git

# Option 2: clone and install
git clone https://github.com/Sophomoresty/doifans-dl.git
cd doifans-dl
pip install .
```

### Usage

```bash
# Download all videos from a creator
doifans-dl --proxy http://127.0.0.1:7890 ouyangqin

# List video URLs only (JSON output)
doifans-dl --proxy http://127.0.0.1:7890 hongkongdoll --list

# Custom output directory
doifans-dl --proxy http://127.0.0.1:7890 wantingwan -o ~/Videos

# Check connectivity
doifans-dl --proxy http://127.0.0.1:7890 doctor
```

### How it works

| Step | Vulnerability | Endpoint |
|------|--------------|----------|
| 1. Fund wallet | Stripe webhook forgery (no signature verification) | `POST /stripe/webhook` |
| 2. Login | WAF bypass via JSON Content-Type | `POST /login` |
| 3. Subscribe | WAF bypass via wallet payment gateway | `POST /buy/subscription` |
| 4. Scrape URLs | Authenticated page + AJAX pagination | `GET /<username>`, `GET /ajax/updates` |
| 5. Download | Unauthenticated static file access | `GET /public/uploads*/updates/videos/*.mp4` |

### Additional vulnerabilities found (not used by this tool)

| Vulnerability | Endpoint | Impact |
|---------------|----------|--------|
| Laravel debug mode | `APP_DEBUG=true` | Full source code & SQL query exposure via Ignition |
| Public log file | `/storage/logs/laravel.log` | Password hashes, user emails, session data |
| Mass assignment | `POST /settings/page` | Modify user fields (password, stripe_id, etc.) |
| WAF bypass (trailing slash) | `POST /subscription/free/` | Free subscription to any creator |
| PHP execution on config files | `GET /config/app.php` | Direct PHP-FPM execution of config files |

### Disclaimer

For educational and authorized security research purposes only. The authors are not responsible for any misuse.
