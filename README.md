# doifans-dl

Paywall bypass video downloader for [doifans.vip](https://doifans.vip).

## How it works

doifans.vip is a Sponzy v4.6 (OnlyFans clone) instance with several critical vulnerabilities:

1. **Stripe webhook forgery** — The `/stripe/webhook` endpoint has no signature verification. A forged `checkout.session.completed` event credits arbitrary wallet funds to any user.
2. **WAF bypass** — Login uses JSON `Content-Type` to bypass nginx WAF rules that block form-encoded POST with `password=` in body.
3. **Wallet subscription** — The `payment_gateway=wallet` option on `/buy/subscription` is not blocked by WAF, allowing subscription purchase with forged funds.
4. **Unauthenticated file access** — nginx serves video files at `/public/uploads/updates/videos/` and `/public/uploads_new/updates/videos/` without any authentication check.

The tool chains these together: forge funds → subscribe → scrape video URLs → download directly.

## Install

```bash
pip install requests
```

## Usage

```bash
# Download all videos from a creator
python doifans_dl.py ouyangqin

# List video URLs without downloading
python doifans_dl.py hongkongdoll --list

# Custom output directory
python doifans_dl.py wantingwan -o ~/Videos

# Use a proxy
python doifans_dl.py ouyangqin --proxy http://127.0.0.1:7899
```

## Tested creators

| Creator | Videos | Total size |
|---------|--------|-----------|
| ouyangqin | 23 | ~2.2 GB |
| hongkongdoll | 20 | — |
| wantingwan | 123 | — |

## Vulnerabilities exploited

| Vuln | Endpoint | Impact |
|------|----------|--------|
| Webhook forgery (no Stripe signature) | `POST /stripe/webhook` | Unlimited wallet credit |
| WAF bypass (JSON content-type) | `POST /login` | Authentication |
| WAF bypass (wallet gateway) | `POST /buy/subscription` | Free subscriptions |
| Unauthenticated static files | `/public/uploads*/updates/videos/*.mp4` | Direct download |
| Debug mode enabled | `APP_DEBUG=true` | Source code & SQL leak via Ignition |
| Public log file | `/storage/logs/laravel.log` | Password hashes, user data |

## Disclaimer

For educational and authorized security research purposes only.
