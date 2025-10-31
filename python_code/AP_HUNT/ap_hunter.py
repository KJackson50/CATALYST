import csv
import os
import re
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException


# ---- Helpers -------------------------------------------------------------------------------------

SHORTEN_MAP = {
    "GigabitEthernet": "Gi",
    "TenGigabitEthernet": "Te",
    "TwentyFiveGigE": "Twe",      # seen on some platforms
    "FortyGigabitEthernet": "Fo",
    "HundredGigE": "Hu",
    "FastEthernet": "Fa",
    "TwoGigabitEthernet": "Tw",
    "AppGigabitEthernet": "Ap",
    "Ethernet": "Eth",
}

def norm_intf(name: str) -> str:
    """
    Normalize interface names so 'GigabitEthernet1/0/1' and 'Gi1/0/1' match.
    - trims spaces
    - titlecase long names to consistent map
    - converts long names to Cisco short forms (Gi/Te/Fa, etc.)
    - uppercases final
    """
    if not name:
        return ""
    s = name.strip()
    # remove trailing commas/colons common in outputs
    s = s.rstrip(",:")
    # compress multiple spaces
    s = re.sub(r"\s+", "", s)

    # If already looks short (Gi1/0/1), just uppercase Gi->GI for stable compare
    m = re.match(r"^[A-Za-z]{1,3}\d", s)
    if m:
        return s[:2].capitalize() + s[2:]  # keep Gi/Te/Hu casing consistent

    # Try replacing long names to short
    for long, short in SHORTEN_MAP.items():
        if s.startswith(long):
            return short + s[len(long):]
    return s  # fallback unchanged


def parse_poe_on(output: str) -> set:
    """
    Parse 'show power inline' output.
    We accept any line where the operational state shows 'on'.
    Works with table lines like:
    Gi1/0/1  auto   on   15.4   Ieee PD   4     30.0
    """
    poe_on = set()
    for line in output.splitlines():
        # quick pass: must start with an interface token
        line = line.strip()
        if not line or line.lower().startswith(("interface", "module", "device", "system", "available", "max", "admin", "----")):
            continue
        # Find a leading interface token
        m = re.match(r"^(?P<intf>[A-Za-z][A-Za-z0-9/._-]+)\s+.*?\b(on)\b", line, flags=re.IGNORECASE)
        if m:
            poe_on.add(norm_intf(m.group("intf")))
    return poe_on


def parse_lldp_local_intf(output: str) -> set:
    """
    Parse 'show lldp neighbors' (summary) output to collect Local Intf column.
    Typical table rows start with Local Intf in column 1.
    Also supports 'show lldp neighbors detail' by detecting 'Local Intf:' lines.
    """
    lldp_ports = set()
    lines = output.splitlines()

    # Try 'detail' style first
    for line in lines:
        dm = re.search(r"Local\s+Intf\s*:\s*([A-Za-z0-9/._-]+)", line, flags=re.IGNORECASE)
        if dm:
            lldp_ports.add(norm_intf(dm.group(1)))

    if lldp_ports:
        return lldp_ports

    # Summary table style: header contains 'Local Intf'
    header_idx = None
    for i, line in enumerate(lines):
        if re.search(r"\bLocal\s+Intf\b", line, flags=re.IGNORECASE):
            header_idx = i
            break

    # After header, rows usually begin with interface names until a blank
    if header_idx is not None:
        for line in lines[header_idx + 1:]:
            if not line.strip():
                continue
            # stop at separators or non-table content
            if re.match(r"^-{3,}|={3,}", line):
                continue
            # First column token should be the local interface
            first = line.strip().split()[0]
            # Must look like an interface
            if re.match(r"^[A-Za-z][A-Za-z0-9/._-]+$", first):
                lldp_ports.add(norm_intf(first))
    return lldp_ports


def ensure_dir(path: str):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


# ---- Worker --------------------------------------------------------------------------------------

def process_switch(host: str, username: str, password: str, device_type: str, outdir: str, timeout: int = 20):
    result = {
        "host": host,
        "ok": False,
        "error": "",
        "poe_on": set(),
        "lldp_ports": set(),
        "suspects": [],  # list of (host, interface)
    }
    try:
        conn = ConnectHandler(
            device_type=device_type,
            host=host,
            username=username,
            password=password,
            fast_cli=False,
            timeout=timeout,
        )

        # Some platforms need terminal length 0 to avoid paging
        try:
            conn.send_command("terminal length 0", expect_string=r"#", strip_prompt=False, strip_command=False)
        except Exception:
            pass

        # Collect commands
        poe_raw = conn.send_command("show power inline", expect_string=r"#")
        lldp_raw = conn.send_command("show lldp neighbors", expect_string=r"#")

        conn.disconnect()

        # Parse
        poe_on = parse_poe_on(poe_raw)
        lldp_ports = parse_lldp_local_intf(lldp_raw)

        result["poe_on"] = poe_on
        result["lldp_ports"] = lldp_ports

        # Write raw lists
        base = os.path.join(outdir, host)
        ensure_dir(outdir)

        with open(f"{base}_poe_on.txt", "w", encoding="utf-8") as f:
            for p in sorted(poe_on):
                f.write(p + "\n")

        with open(f"{base}_lldp_local.txt", "w", encoding="utf-8") as f:
            for p in sorted(lldp_ports):
                f.write(p + "\n")

        # Diff: PoE ON but NO LLDP
        suspects = sorted(poe_on - lldp_ports)
        result["suspects"] = [(host, iface) for iface in suspects]

        # Per-switch CSV
        with open(f"{base}_suspects.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["switch", "interface", "reason"])
            for _, iface in result["suspects"]:
                w.writerow([host, iface, "PoE on, no LLDP neighbor"])

        result["ok"] = True
        return result

    except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
        result["error"] = f"{type(e).__name__}: {e}"
    except Exception as e:
        result["error"] = f"Unhandled error: {e}"
    return result


# ---- Main ----------------------------------------------------------------------------------------

def load_inventory(path: str):
    devices = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            devices.append({
                "host": row["host"].strip(),
                "username": row["username"].strip(),
                "password": row.get("password", "").strip(),  # can be blank
                "device_type": row.get("device_type", "cisco_xe").strip() or "cisco_xe",
            })
    return devices



def main():
    ap = argparse.ArgumentParser(description="Hunt ports powering devices with no LLDP neighbor (suspect APs).")
    ap.add_argument("--inventory", required=True, help="CSV with columns: host,username,password,device_type")
    ap.add_argument("--out", default="./aphunt_out", help="Output directory (default: ./aphunt_out)")
    ap.add_argument("--workers", type=int, default=8, help="Parallel workers (default: 8)")
    ap.add_argument("--timeout", type=int, default=20, help="SSH timeout seconds (default: 20)")
    args = ap.parse_args()

    ensure_dir(args.out)
    devices = load_inventory(args.inventory)
    from getpass import getpass
    # Prompt once for password if any device is missing one
    if any(not d["password"] for d in devices):
     shared_password = getpass("Enter switch password: ")
    for d in devices:
        if not d["password"]:
            d["password"] = shared_password

    if not devices:
        print("No devices loaded from inventory.", file=sys.stderr)
        sys.exit(2)

    combined = []
    errors = []

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [
            ex.submit(
                process_switch,
                d["host"], d["username"], d["password"], d["device_type"],
                args.out, args.timeout
            )
            for d in devices
        ]
        for fut in as_completed(futs):
            res = fut.result()
            host = res["host"]
            if res["ok"]:
                combined.extend(res["suspects"])
                print(f"[OK] {host}: {len(res['suspects'])} suspect port(s)")
            else:
                errors.append((host, res["error"]))
                print(f"[ERR] {host}: {res['error']}", file=sys.stderr)

    # Combined CSV
    combined_path = os.path.join(args.out, "combined_all_suspects.csv")
    with open(combined_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["switch", "interface", "reason", "timestamp"])
        ts = datetime.utcnow().isoformat() + "Z"
        for host, iface in sorted(combined):
            w.writerow([host, iface, "PoE on, no LLDP neighbor", ts])

    print(f"\nWrote combined suspects: {combined_path}")

    if errors:
        err_path = os.path.join(args.out, "errors.log")
        with open(err_path, "w", encoding="utf-8") as f:
            for host, msg in errors:
                f.write(f"{host}: {msg}\n")
        print(f"Wrote errors: {err_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
