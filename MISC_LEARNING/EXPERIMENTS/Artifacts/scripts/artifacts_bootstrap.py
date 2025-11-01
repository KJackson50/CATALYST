#!/usr/bin/env python3
# artifacts_bootstrap.py
# Purpose: Verify Artifacts API token, list your characters, and (optionally) peek at bank items or demo a move action.
# Depends on: Artifacts public API (https://api.artifactsmmo.com)
# Usage:
#   python artifacts_bootstrap.py                # token via ARTIFACTS_TOKEN env var or prompt
#   python artifacts_bootstrap.py --bank         # also fetches your bank items
#   python artifacts_bootstrap.py --move NAME --x 4 --y -1   # demo: move a character (optional)

import os, sys, json, argparse
import requests

API_BASE = "https://api.artifactsmmo.com"
TIMEOUT  = 30

def bearer_token():
    token_file = os.path.expanduser("~/Artifacts/token.txt")  # or absolute path
    if os.path.exists(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            tok = f.read().strip()
            if tok:
                return tok
    # fallback prompt
    tok = input("Enter your Artifacts API token: ").strip()
    if tok:
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(tok)
        print(f"[+] Saved token to {token_file}")
    return tok


def api_get(path, token, params=None):
    url = f"{API_BASE}{path}"
    r = requests.get(url, headers={
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }, params=params, timeout=TIMEOUT)
    _check(r, url)
    return r.json()

def api_post(path, token, payload):
    url = f"{API_BASE}{path}"
    r = requests.post(url, headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }, json=payload, timeout=TIMEOUT)
    _check(r, url)
    return r.json()

def _check(r, url):
    if not r.ok:
        print(f"[!] HTTP {r.status_code} for {url}")
        try:
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text[:500])
        sys.exit(1)

def list_characters(token):
    data = api_get("/my/characters", token, params={"page": 1, "size": 50})
    chars = data.get("data") or data.get("content") or data  # schema convenience
    rows = []
    if isinstance(chars, list):
        for c in chars:
            # Grab a few common fields safely
            name = c.get("name") or c.get("character") or "?"
            lvl  = c.get("level") or c.get("combat_level") or c.get("lvl")
            pos  = c.get("position") or c.get("map") or {}
            x    = (pos or {}).get("x")
            y    = (pos or {}).get("y")
            rows.append({"name": name, "level": lvl, "x": x, "y": y})
    return rows

def get_bank_items(token, item_code=None):
    params = {"item_code": item_code} if item_code else None
    data = api_get("/my/bank/items", token, params=params)
    items = data.get("data") or data.get("items") or data
    rows = []
    if isinstance(items, list):
        for it in items:
            rows.append({
                "slot": it.get("slot"),
                "code": it.get("code") or it.get("item_code"),
                "qty": it.get("quantity") or it.get("qty")
            })
    return rows

def move_character(token, name, x=None, y=None, map_id=None):
    if map_id is not None:
        payload = {"map_id": int(map_id)}
    else:
        if x is None or y is None:
            print("[!] For move: provide --x and --y or --map-id")
            sys.exit(1)
        payload = {"x": int(x), "y": int(y)}
    return api_post(f"/my/{name}/action/move", token, payload)

def main():
    ap = argparse.ArgumentParser(description="Artifacts quick bootstrap")
    ap.add_argument("--bank", action="store_true", help="Also list bank items")
    ap.add_argument("--item-code", help="Filter bank by item code")
    ap.add_argument("--move", metavar="NAME", help="Demo: move this character (caution: performs an action)")
    ap.add_argument("--x", type=int, help="Target X (for --move)")
    ap.add_argument("--y", type=int, help="Target Y (for --move)")
    ap.add_argument("--map-id", type=int, help="Target map_id (alternative to x/y)")
    args = ap.parse_args()

    token = bearer_token()

    # 1) List characters
    chars = list_characters(token)
    if not chars:
        print("[!] No characters found. Create one in the web client, then re-run.")
        sys.exit(0)

    print("\n== Your Characters ==")
    for c in chars:
        print(f"{c['name']:<18} level={c['level']}  pos=({c['x']},{c['y']})")

    # 2) Optional: bank items
    if args.bank:
        items = get_bank_items(token, item_code=args.item_code)
        print("\n== Bank Items ==")
        if not items:
            print("(empty)")
        else:
            for it in items[:50]:
                print(f"slot={it['slot']}, code={it['code']}, qty={it['qty']}")
            if len(items) > 50:
                print(f"... {len(items)-50} more")

    # 3) Optional: demo move (safe toggle; comment this out if you don't want accidental moves)
    if args.move:
        print(f"\n[>] Moving {args.move} ...")
        res = move_character(token, args.move, x=args.x, y=args.y, map_id=args.map_id)
        # Show minimal confirmation
        print(json.dumps(res, indent=2)[:1200])

if __name__ == "__main__":
    main()
