"""CLI entrypoint for doifans-dl."""

import argparse
import json
import sys
from pathlib import Path

from doifans_dl.client import DoiFans


def main():
    ap = argparse.ArgumentParser(prog="doifans-dl", description="DoiFans paywall bypass downloader")
    ap.add_argument("creator", help="Creator username or 'doctor' to check connectivity")
    ap.add_argument("-o", "--output", default="./downloads", help="Output directory")
    ap.add_argument("--list", action="store_true", help="List video URLs as JSON, don't download")
    ap.add_argument("--proxy", help="HTTP/SOCKS proxy URL")
    ap.add_argument("--user", default=None, help="Login username (default: built-in)")
    ap.add_argument("--password", default=None, help="Login password (default: built-in)")
    ap.add_argument("--cookie", default=None, help="Session cookie string (doifans_session=xxx) or path to cookie file")
    ap.add_argument("--json", action="store_true", help="JSON output (default for --list)")
    ap.add_argument("--text", action="store_true", help="Human-readable output")
    args = ap.parse_args()
    args.cmd = "doctor" if args.creator == "doctor" else None

    client = DoiFans(proxy=args.proxy)
    use_json = args.json or (args.list and not args.text)

    if args.cmd == "doctor":
        ok = client.login(args.user, args.password)
        result = {"auth": ok, "proxy": args.proxy or "none", "base": client.base}
        if use_json or not args.text:
            print(json.dumps(result))
        else:
            print(f"Auth: {'ok' if ok else 'FAIL'}")
            print(f"Proxy: {args.proxy or 'none'}")
        sys.exit(0 if ok else 1)

    if not args.creator:
        ap.print_help()
        sys.exit(1)

    if args.cookie:
        if not client.login_with_cookie(args.cookie):
            _out(use_json, {"error": "cookie_invalid"}, "[-] Cookie login failed")
            sys.exit(1)
    elif not client.login(args.user, args.password):
        _out(use_json, {"error": "login_failed"}, "[-] Login failed")
        sys.exit(1)

    cid, total = client.resolve_creator(args.creator)
    if not cid:
        _out(use_json, {"error": "creator_not_found", "username": args.creator},
             f"[-] Creator '{args.creator}' not found")
        sys.exit(1)

    client.fund_wallet()
    client.subscribe(cid)
    videos = client.scrape_videos(args.creator)

    if args.list:
        _out(use_json,
             {"creator": args.creator, "id": cid, "total_posts": total, "videos": videos},
             "\n".join(videos) if videos else "No videos found")
        sys.exit(0)

    out_dir = Path(args.output) / args.creator
    results = client.download(videos, out_dir)
    ok_count = sum(1 for r in results if r["status"] in ("ok", "skipped"))

    if use_json:
        print(json.dumps({"creator": args.creator, "id": cid, "downloaded": ok_count,
                          "total": len(videos), "output": str(out_dir), "files": results}))
    else:
        for r in results:
            tag = "ok" if r["status"] == "ok" else r["status"]
            size_mb = r.get("size", 0) / 1048576
            print(f"  [{tag}] {Path(r['file']).name} ({size_mb:.1f} MB)")
        print(f"\n[+] {ok_count}/{len(videos)} → {out_dir}")


def _out(use_json, obj, text):
    if use_json:
        print(json.dumps(obj))
    else:
        print(text)


if __name__ == "__main__":
    main()
