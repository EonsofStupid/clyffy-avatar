#!/usr/bin/env python3
"""Stateless render worker + job submitter, coordinated through a shared spool directory.

    clyffy worker                       # poll the spool and render jobs (run N of these)
    clyffy submit [BLEND] [--res WxH] [--samples N] [--engine E] [--wait]

The spool ($CLYFFY_SPOOL, default /data/jobs) and the output dir ($CLYFFY_OUT, default
/data/out) are named volumes, so any number of workers (`docker compose up --scale worker=N`)
share them. A worker claims a job with an atomic rename(2) from pending/ to running/, so two
workers never take the same job. Results land in done/<id>.json (or failed/<id>.json) and the
image in $CLYFFY_OUT/<id>.png. Workers hold no state of their own.
"""
import argparse, json, os, socket, subprocess, sys, time, uuid
from pathlib import Path

ROOT = Path(os.environ.get("CLYFFY_ROOT", Path(__file__).resolve().parents[1]))
SPOOL = Path(os.environ.get("CLYFFY_SPOOL", "/data/jobs"))
OUT = Path(os.environ.get("CLYFFY_OUT", "/data/out"))
BLENDER = os.environ.get("BLENDER", "blender")
HEARTBEAT = Path(os.environ.get("CLYFFY_HEARTBEAT", "/tmp/clyffy-worker.heartbeat"))
DIRS = ("pending", "running", "done", "failed", "tmp")


def spool():
    for d in DIRS:
        (SPOOL / d).mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)


def render(job, worker):
    out = OUT / f"{job['id']}.png"
    env = dict(os.environ)
    for k, envk in (("res", "CLYFFY_RES"), ("samples", "CLYFFY_SAMPLES"),
                    ("engine", "CLYFFY_ENGINE"), ("device", "CLYFFY_CYCLES_DEVICE")):
        if job.get(k):
            env[envk] = str(job[k])
    blend = job.get("blend") or "work/RETOPO_clyffy.blend"
    cmd = [BLENDER, "-b"] + ([blend] if blend != "-" else ["--factory-startup"]) + \
          ["--python", str(ROOT / "scripts/render_still.py"), "--", str(out)]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    log = (p.stdout + p.stderr)[-4000:]
    device = next((l.split("Cycles device:", 1)[1].strip() for l in log.splitlines() if "Cycles device:" in l), None)
    ok = p.returncode == 0 and out.is_file() and out.stat().st_size > 0
    return {**job, "status": "done" if ok else "failed", "returncode": p.returncode,
            "out": str(out) if ok else None, "bytes": out.stat().st_size if ok else 0,
            "seconds": round(time.time() - t0, 2), "worker": worker, "device": device,
            "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "log_tail": log[-1500:]}


def worker(poll):
    spool()
    me = socket.gethostname()
    print(f"clyffy worker {me}: spool={SPOOL} out={OUT} device={os.environ.get('CLYFFY_CYCLES_DEVICE', 'CPU')}", flush=True)
    while True:
        HEARTBEAT.write_text(str(time.time()))
        for f in sorted((SPOOL / "pending").glob("*.json")):
            claimed = SPOOL / "running" / f"{f.stem}.{me}.json"
            try:
                os.rename(f, claimed)
            except (FileNotFoundError, OSError):
                continue  # another worker won the race
            job = json.loads(claimed.read_text())
            print(f"[{me}] job {job['id']}: {job.get('blend')}", flush=True)
            res = render(job, me)
            dest = SPOOL / res["status"] / f"{job['id']}.json"
            tmp = SPOOL / "tmp" / f"{job['id']}.{me}.json"
            tmp.write_text(json.dumps(res, indent=2))
            os.rename(tmp, dest)
            claimed.unlink(missing_ok=True)
            print(f"[{me}] job {job['id']}: {res['status']} in {res['seconds']}s -> {res['out']}", flush=True)
            HEARTBEAT.write_text(str(time.time()))
        time.sleep(poll)


def submit(a):
    spool()
    jid = a.id or time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    job = {"id": jid, "blend": a.blend, "res": a.res, "samples": a.samples,
           "engine": a.engine, "device": a.device, "submitted": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    tmp = SPOOL / "tmp" / f"{jid}.json"
    tmp.write_text(json.dumps(job))
    os.rename(tmp, SPOOL / "pending" / f"{jid}.json")
    print(jid, flush=True)
    if not a.wait:
        return 0
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        for st in ("done", "failed"):
            r = SPOOL / st / f"{jid}.json"
            if r.is_file():
                res = json.loads(r.read_text())
                res.pop("log_tail", None) if st == "done" else None
                print(json.dumps(res, indent=2))
                return 0 if st == "done" else 1
        time.sleep(1)
    print(f"timeout waiting for {jid}", file=sys.stderr)
    return 3


def main():
    ap = argparse.ArgumentParser(prog="clyffy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worker"); w.add_argument("--poll", type=float, default=float(os.environ.get("CLYFFY_WORKER_POLL", "2")))
    s = sub.add_parser("submit")
    s.add_argument("blend", nargs="?", default="work/RETOPO_clyffy.blend", help="repo-relative .blend, or - for an empty test scene")
    s.add_argument("--res"); s.add_argument("--samples", type=int); s.add_argument("--engine"); s.add_argument("--device")
    s.add_argument("--id"); s.add_argument("--wait", action="store_true"); s.add_argument("--timeout", type=float, default=1800)
    a = ap.parse_args()
    if a.cmd == "worker":
        worker(a.poll)
    sys.exit(submit(a))


if __name__ == "__main__":
    main()
