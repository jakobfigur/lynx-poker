"""Hetzner Cloud fuer Lynx-Rechenlaeufe, ohne hcloud-CLI (nur Standardbibliothek).

Token: data/cloud/hetzner.token, SSH-Schluessel data/cloud/lynx_hetzner(.pub), bei Hetzner als "lynx-hetzner".
Server existieren nur fuer den jeweiligen Lauf; `delete` am Ende nicht vergessen (`list` zeigt laufende Kosten).

  python cloud/hetzner.py types                      Servertypen mit Preis je Kern-Stunde
  python cloud/hetzner.py list                       Server, Laufzeit, bisherige Kosten
  python cloud/hetzner.py create NAME [--type cx53] [--location nbg1] [--image ubuntu-24.04]
                                                     legt an, wartet auf "running" + SSH, richtet den Server ein
                                                     (cloud/server-setup.sh) und kopiert den Code (push)
  python cloud/hetzner.py push NAME                  Code (collector ohne .venv/data, pc.sh, cloud/*.sh) hochladen
  python cloud/hetzner.py ssh NAME [BEFEHL ...]      Shell bzw. Befehl auf dem Server
  python cloud/hetzner.py pull NAME REMOTE LOKAL     Dateien/Ordner zurueckholen (scp -r)
  python cloud/hetzner.py delete NAME|--all          Server loeschen (Kosten enden sofort)

Windows: Aufruf mit dem Projekt-Python, z. B.
  tools\\python\\cpython-3.12.12-windows-x86_64-none\\python.exe cloud\\hetzner.py list
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOUD_DIR = ROOT / "data" / "cloud"
TOKEN_FILE = CLOUD_DIR / "hetzner.token"
KEY_FILE = CLOUD_DIR / "lynx_hetzner"
SSH_KEY_NAME = "lynx-hetzner"
API = "https://api.hetzner.cloud/v1"
REMOTE_DIR = "/opt/lynx"
LABELS = {"project": "lynx"}


def token() -> str:
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        sys.exit(f"Token fehlt: {TOKEN_FILE}")


def api(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json",
                                          "User-Agent": "lynx-hetzner/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        sys.exit(f"Hetzner-API {method} {path}: HTTP {e.code}: {msg[:400]}")


def hourly_gross(server_type: dict, location: str) -> float | None:
    for p in server_type["prices"]:
        if p["location"] == location:
            return float(p["price_hourly"]["gross"])
    return None


def available(server_type: dict, location: str) -> bool:
    """Ist der Typ am Standort gerade bestellbar? (Die cx-Reihe ist oft ausverkauft: HTTP 412 resource_unavailable.)"""
    return any(l["name"] == location and l.get("available") for l in server_type.get("locations", []))


def cmd_types(a):
    rows = []
    for t in api("GET", "/server_types?per_page=50")["server_types"]:
        if t["deprecated"] or t["architecture"] != "x86":
            continue
        h = hourly_gross(t, a.location)
        if h is None:
            continue
        rows.append((h / t["cores"], t["name"], t["cores"], t["cpu_type"], t["memory"], h, available(t, a.location)))
    print(f"{'Typ':8} {'Kerne':>5} {'CPU':9} {'RAM':>6} {'EUR/h':>8} {'ct/Kern-h':>10}  bestellbar  ({a.location}, brutto)")
    for r in sorted(rows):
        print(f"{r[1]:8} {r[2]:5} {r[3]:9} {r[4]:5.0f}G {r[5]:8.4f} {r[0] * 100:10.2f}  {'ja' if r[6] else 'NEIN':>10}")


def servers() -> list[dict]:
    return api("GET", "/servers?per_page=50")["servers"]


def find(name: str) -> dict:
    for s in servers():
        if s["name"] == name:
            return s
    sys.exit(f"kein Server namens {name!r} (vorhanden: {[s['name'] for s in servers()]})")


def ip_of(s: dict) -> str:
    return s["public_net"]["ipv4"]["ip"]


def _loc(s: dict) -> str:
    """Standortname eines Servers (API seit 2025: 'location' statt 'datacenter.location')."""
    if s.get("location"):
        return s["location"]["name"]
    return s.get("datacenter", {}).get("location", {}).get("name", "?")


def cmd_list(a):
    ss = servers()
    if not ss:
        print("keine Server (keine laufenden Kosten)")
        return
    total = 0.0
    for s in ss:
        created = datetime.fromisoformat(s["created"].replace("Z", "+00:00"))
        hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600
        price = hourly_gross(s["server_type"], _loc(s)) or 0.0
        cost = hours * price
        total += cost
        print(f"{s['name']:16} {s['server_type']['name']:7} {s['status']:9} {ip_of(s):15} "
              f"seit {hours:5.1f} h  ~{cost:5.2f} EUR  ({_loc(s)})")
    print(f"zusammen ~{total:.2f} EUR brutto bisher")


def ssh_base(ip: str) -> list[str]:
    return ["ssh", "-i", str(KEY_FILE), "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15",
            "-o", "BatchMode=yes",      # nie nach Passwort/Bestaetigung fragen (haengt sonst ohne Konsole, 30.10.)
            "-o", "ServerAliveInterval=30", f"root@{ip}"]


def run_ssh(ip: str, cmd: str, check: bool = True, quiet: bool = False) -> int:
    r = subprocess.run(ssh_base(ip) + [cmd], stdout=subprocess.DEVNULL if quiet else None,
                       stderr=subprocess.DEVNULL if quiet else None)
    if check and r.returncode:
        sys.exit(f"ssh-Befehl schlug fehl ({r.returncode}): {cmd}")
    return r.returncode


def wait_ssh(ip: str, timeout: float = 300) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if run_ssh(ip, "true", check=False, quiet=True) == 0:
            return
        time.sleep(5)
    sys.exit(f"SSH auf {ip} nach {timeout:.0f} s nicht erreichbar")


def cmd_create(a):
    for s in servers():
        if s["name"] == a.name:
            sys.exit(f"Server {a.name} existiert schon ({ip_of(s)}); erst loeschen oder anderen Namen waehlen")
    keys = api("GET", "/ssh_keys")["ssh_keys"]
    if not any(k["name"] == SSH_KEY_NAME for k in keys):
        pub = (KEY_FILE.with_suffix(".pub")).read_text(encoding="utf-8").strip()
        api("POST", "/ssh_keys", {"name": SSH_KEY_NAME, "public_key": pub, "labels": LABELS})
        print(f"SSH-Schluessel {SSH_KEY_NAME} bei Hetzner hinterlegt")
    types = {t["name"]: t for t in api("GET", "/server_types?per_page=50")["server_types"]}
    if a.type in types and not available(types[a.type], a.location):
        alt = sorted((hourly_gross(t, a.location) / t["cores"], t["name"], t["cores"], hourly_gross(t, a.location))
                     for t in types.values() if not t["deprecated"] and t["architecture"] == "x86"
                     and t["cores"] >= 8 and available(t, a.location) and hourly_gross(t, a.location) is not None)
        hint = ", ".join(f"{n} ({c} Kerne, {h:.4f} EUR/h)" for _, n, c, h in alt[:4]) or "keiner mit >= 8 Kernen"
        sys.exit(f"{a.type} ist in {a.location} gerade nicht bestellbar (ausverkauft). Bestellbar: {hint}")
    body = {"name": a.name, "server_type": a.type, "image": a.image, "location": a.location,
            "ssh_keys": [SSH_KEY_NAME], "labels": LABELS, "start_after_create": True,
            "public_net": {"enable_ipv4": True, "enable_ipv6": False}}
    res = api("POST", "/servers", body)
    s = res["server"]
    ip = ip_of(s)
    print(f"Server {a.name} ({a.type}, {a.location}) angelegt, IP {ip}, Status {s['status']} ...", flush=True)
    t0 = time.time()
    while s["status"] != "running":
        time.sleep(5)
        s = api("GET", f"/servers/{s['id']}")["server"]
        if time.time() - t0 > 300:
            sys.exit("Server kommt nicht in den Zustand running")
    print(f"laeuft nach {time.time() - t0:.0f} s, warte auf SSH ...", flush=True)
    # Hetzner vergibt IPs schnell wieder: alter Host-Schluessel in known_hosts -> ssh verweigert (30.10., 5 min verloren)
    subprocess.run(["ssh-keygen", "-R", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_ssh(ip)
    if not a.no_setup:
        do_push(ip)
        print("Einrichtung (apt, uv, Abhaengigkeiten) laeuft, dauert einige Minuten ...", flush=True)
        run_ssh(ip, f"bash {REMOTE_DIR}/cloud/server-setup.sh")
    print(f"fertig: ssh -i {KEY_FILE} root@{ip}")
    print(f"Kosten: {hourly_gross(s['server_type'], a.location):.4f} EUR/h brutto, bis `hetzner.py delete {a.name}`")


def do_push(ip: str) -> None:
    def keep(ti: tarfile.TarInfo):
        parts = Path(ti.name).parts
        if any(p in (".venv", "__pycache__", ".pytest_cache", "data", "tools") for p in parts):
            return None
        if ti.name.endswith((".pyc", ".npz", ".pt", ".jsonl")):
            return None
        return ti
    with tempfile.TemporaryDirectory() as td:
        tgz = Path(td) / "lynx-code.tgz"
        with tarfile.open(tgz, "w:gz") as tf:
            tf.add(ROOT / "collector", arcname="collector", filter=keep)
            tf.add(ROOT / "pc.sh", arcname="pc.sh")
            tf.add(ROOT / "cloud", arcname="cloud", filter=keep)
        size = tgz.stat().st_size / 1e6
        print(f"Code-Archiv {size:.1f} MB -> {ip}:{REMOTE_DIR}", flush=True)
        run_ssh(ip, f"mkdir -p {REMOTE_DIR} {REMOTE_DIR}/data/valuenet")
        r = subprocess.run(["scp", "-i", str(KEY_FILE), "-o", "StrictHostKeyChecking=accept-new", str(tgz),
                            f"root@{ip}:{REMOTE_DIR}/lynx-code.tgz"])
        if r.returncode:
            sys.exit("scp schlug fehl")
        run_ssh(ip, f"cd {REMOTE_DIR} && tar xzf lynx-code.tgz && rm lynx-code.tgz && chmod +x pc.sh cloud/*.sh")


def cmd_push(a):
    do_push(ip_of(find(a.name)))


def cmd_ssh(a):
    ip = ip_of(find(a.name))
    cmd = ssh_base(ip) + ([" ".join(a.cmd)] if a.cmd else [])
    sys.exit(subprocess.call(cmd))


def remote_path(p: str) -> str:
    """Git-Bash (MSYS) wandelt Argumente wie /opt/lynx/... in C:/Users/.../Git/opt/lynx/... um - rueckgaengig machen.
    (30.10.: so ging der 1000er-Test verloren, scp fand den Pfad nicht und der Server war schon geloescht.)"""
    if not p.startswith("/") and "/opt/" in p:
        return p[p.index("/opt/"):]
    return p


def cmd_pull(a):
    ip = ip_of(find(a.name))
    remote = remote_path(a.remote)
    Path(a.local).mkdir(parents=True, exist_ok=True)
    before = {q.name for q in Path(a.local).iterdir()}
    r = subprocess.run(["scp", "-i", str(KEY_FILE), "-o", "StrictHostKeyChecking=accept-new", "-o", "BatchMode=yes",
                        "-r", f"root@{ip}:{remote}", a.local])
    after = {q.name for q in Path(a.local).iterdir()}
    if r.returncode != 0 or after == before:
        sys.exit(f"pull fehlgeschlagen (scp exit {r.returncode}, nichts Neues in {a.local}) - Server NICHT loeschen")
    print(f"geholt nach {a.local}: {sorted(after - before)}")


def cmd_delete(a):
    targets = servers() if a.all else [find(a.name)]
    if not targets:
        print("nichts zu loeschen")
        return
    for s in targets:
        api("DELETE", f"/servers/{s['id']}")
        print(f"Server {s['name']} ({ip_of(s)}) geloescht")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("types"); p.add_argument("--location", default="nbg1"); p.set_defaults(fn=cmd_types)
    p = sub.add_parser("list"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("create"); p.add_argument("name"); p.add_argument("--type", default="cx53")
    p.add_argument("--location", default="nbg1"); p.add_argument("--image", default="ubuntu-24.04")
    p.add_argument("--no-setup", action="store_true", help="nur anlegen, kein push/setup"); p.set_defaults(fn=cmd_create)
    p = sub.add_parser("push"); p.add_argument("name"); p.set_defaults(fn=cmd_push)
    p = sub.add_parser("ssh"); p.add_argument("name"); p.add_argument("cmd", nargs=argparse.REMAINDER)
    p.set_defaults(fn=cmd_ssh)
    p = sub.add_parser("pull"); p.add_argument("name"); p.add_argument("remote"); p.add_argument("local")
    p.set_defaults(fn=cmd_pull)
    p = sub.add_parser("delete"); p.add_argument("name", nargs="?"); p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_delete)
    a = ap.parse_args(argv)
    if a.cmd == "delete" and not a.name and not a.all:
        ap.error("Name oder --all angeben")
    a.fn(a)


if __name__ == "__main__":
    main()
