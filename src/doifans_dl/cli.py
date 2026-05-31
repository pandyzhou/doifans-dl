"""CLI entrypoint for doifans-dl."""

import argparse
import json
import sys
from pathlib import Path

from doifans_dl.client import DoiFans


def main():
    ap = argparse.ArgumentParser(prog="doifans-dl", description="DoiFans paywall bypass downloader")
    ap.add_argument("creator", help="Creator username or 'doctor' to check status")
    ap.add_argument("-o", "--output", default=".", help="Output directory")
    ap.add_argument("--list", action="store_true", help="List videos only, don't download")
    ap.add_argument("--proxy", help="HTTP/SOCKS proxy URL")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--text", action="store_true", help="Human-readable output")
    ap.add_argument("--id", type=int, help="Creator ID (auto-detected if not given)")
    ap.add_argument("--max-attempts", type=int, default=10, help="Max 2FA brute attempts")
    args = ap.parse_args()

    client = DoiFans(proxy=args.proxy)

    if args.creator == "doctor":
        result = client.doctor()
        _out(args.json, result, f"Auth: {result['auth']}\nProxy: {result['proxy']}")
        return

    # Login with 2FA brute force
    print(f"[*] Logging in (2FA brute force, up to {args.max_attempts} attempts)...")
    if not client.login(max_attempts=args.max_attempts):
        print("[!] Login failed after all attempts", file=sys.stderr)
        sys.exit(1)
    print("[+] Authenticated!")

    # Resolve creator ID
    creator_id = args.id
    if not creator_id:
        print(f"[*] Resolving creator ID for '{args.creator}'...")
        creator_id = client.resolve_creator_id(args.creator)
        if not creator_id:
            print(f"[!] Cannot find creator ID for '{args.creator}'", file=sys.stderr)
            sys.exit(1)
        creator_id = int(creator_id)
    print(f"[*] Creator: {args.creator} (id={creator_id})")

    # Subscribe
    print("[*] Subscribing...")
    if client.subscribe(creator_id):
        print("[+] Subscribed!")
    else:
        print("[!] Subscribe failed (may already be subscribed)", file=sys.stderr)

    # Scrape videos
    print("[*] Scraping video URLs...")
    videos = client.scrape_videos(args.creator, creator_id)
    print(f"[+] Found {len(videos)} videos")

    if args.list:
        _out(args.json, videos, "\n".join(videos))
        return

    # Download
    out_dir = Path(args.output) / args.creator
    print(f"[*] Downloading to {out_dir}...")
    results = client.download_videos(videos, out_dir)
    ok_count = sum(1 for r in results if r["status"] == "ok")
    skip_count = sum(1 for r in results if r["status"] == "skip")

    if args.json:
        print(json.dumps(results))
    else:
        for r in results:
            tag = "✓" if r["status"] == "ok" else "→" if r["status"] == "skip" else "✗"
            size_mb = r.get("size", 0) / 1048576
            print(f"  [{tag}] {Path(r['file']).name} ({size_mb:.1f} MB)")
        print(f"\n[+] {ok_count} downloaded, {skip_count} skipped → {out_dir}")


def _out(use_json, obj, text):
    if use_json:
        print(json.dumps(obj))
    else:
        print(text)


if __name__ == "__main__":
    main()
