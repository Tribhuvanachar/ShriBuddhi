#!/usr/bin/env python3
"""Run Experiment A as a Hugging Face Job (pay-as-you-go GPU on the lead's own HF account) and bring the results back.

    python3 kamadhenu/training/hf_job.py submit  [--flavor l4x1] [--timeout-minutes 150] [--train-cap-minutes 100]
                                                 --commit <sha> [--namespace SarvamulaOrg] [--results-repo …]
    python3 kamadhenu/training/hf_job.py wait    --job <id> [--namespace …]        # streams the log, prints the bill
    python3 kamadhenu/training/hf_job.py collect --results-repo … --out out/       # eval renders, log, run record

Money: an HF Job is billed per second at the flavor's hourly rate (l4x1 = 1× L4 24 GB at $0.80/h, a10g-small $1.00/h)
and is killed at --timeout-minutes, so the worst case is timeout × rate: 150 min on l4x1 = $2.00 ≈ ₹176 at 88/USD —
inside the ₹185 cap the lead approved on 7 Sep 2026; submit refuses anything above --cap-inr. The training loop
inside the job has its own, shorter cap (--train-cap-minutes) so export, evaluation and upload always fit before the
kill. HF_TOKEN comes from the environment (the GitHub secret in CI) and is passed to the job as a secret, never printed.
"""
import argparse, json, os, sys, time
from pathlib import Path

REPO_URL = "https://github.com/Tribhuvanachar/bhumandala.git"
IMAGE = "pytorch/pytorch:2.8.0-cuda12.8-cudnn9-devel"   # the Space's validated torch 2.8 stack; 2.4.1 cannot resolve x-transformers 2.19.7
RATES_USD_PER_HOUR = {"t4-small": 0.40, "t4-medium": 0.60, "l4x1": 0.80, "a10g-small": 1.00, "a10g-large": 1.50, "a100-large": 2.50}
INR_PER_USD = 88.0
SPARSE = ["kamadhenu", "tools/kamadhenu/space", "kamadhenu_dataset"]
TERMINAL = ("COMPLETED", "ERROR", "CANCELED", "DELETED")


def bootstrap_script(commit, train_cap_minutes, results_repo, vram="24GB", precision="bf16"):
    """The command the job runs: minimal system deps, sparse clone at the exact commit, then the same launcher a
    rented box would run. Everything the launcher needs is under the sparse paths (pilot data, refs, manifests)."""
    return "\n".join([
        "set -euo pipefail",
        "export DEBIAN_FRONTEND=noninteractive",
        "(command -v git >/dev/null && command -v ffmpeg >/dev/null) || (apt-get update -qq && apt-get install -y -qq git ffmpeg) || echo 'apt failed; continuing with what the image has'",
        "command -v git || { echo 'git is missing'; exit 2; }",
        "python3 --version; nvcc --version | tail -1 || true",
        "nvidia-smi --query-gpu=name,memory.total --format=csv || true",
        f"git clone --quiet --filter=blob:none --no-checkout {REPO_URL} /repo",
        "cd /repo && git sparse-checkout init --cone && git sparse-checkout set " + " ".join(SPARSE),
        f"git checkout --quiet {commit}",
        "python3 -m pip install -q soundfile numpy imageio-ffmpeg pyyaml datasets huggingface_hub",
        f"export KAMADHENU_VRAM={vram} KAMADHENU_WORK=/work KAMADHENU_MAX_MINUTES={int(train_cap_minutes)} KAMADHENU_RESULTS_REPO={results_repo} KAMADHENU_PRECISION={precision}",
        "bash kamadhenu/training/launch_experiment_a.sh",
    ])


def worst_case(flavor, timeout_minutes):
    usd = RATES_USD_PER_HOUR[flavor] * timeout_minutes / 60
    return round(usd, 2), round(usd * INR_PER_USD)


def cmd_submit(a):
    from huggingface_hub import HfApi
    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("HF_TOKEN is not set")
    usd, inr = worst_case(a.flavor, a.timeout_minutes)
    if inr > a.cap_inr:
        sys.exit(f"worst case ₹{inr} (${usd}) exceeds the approved cap ₹{a.cap_inr}: lower --timeout-minutes or pick a cheaper flavor")
    script = bootstrap_script(a.commit, a.train_cap_minutes, a.results_repo, precision=a.precision)
    api = HfApi(token=token)
    kw = dict(image=IMAGE, command=["bash", "-lc", script], env={"KAMADHENU_JOB": "experiment_a", "PYTHONUNBUFFERED": "1"},
              secrets={"HF_TOKEN": token}, flavor=a.flavor, timeout=int(a.timeout_minutes * 60), name=a.name)
    ns_used, job, err = None, None, None
    for ns in ([a.namespace] if a.namespace else []) + [None]:
        try:
            job = api.run_job(namespace=ns, **kw); ns_used = ns; break
        except Exception as e:  # noqa: BLE001
            err = e; print(f"submit under namespace {ns or '(user)'} failed: {str(e)[:300]}")
    if job is None:
        sys.exit(f"could not submit the job: {err}")
    rec = {"job_id": job.id, "url": job.url, "namespace": ns_used, "flavor": a.flavor, "image": IMAGE, "commit": a.commit,
           "timeout_minutes": a.timeout_minutes, "train_cap_minutes": a.train_cap_minutes, "results_repo": a.results_repo,
           "worst_case_usd": usd, "worst_case_inr": inr, "cap_inr": a.cap_inr, "rate_usd_per_hour": RATES_USD_PER_HOUR[a.flavor],
           "submitted_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    Path(a.record).write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(json.dumps(rec, indent=1))
    if a.github_output:
        with open(a.github_output, "a") as f:
            f.write(f"job_id={job.id}\nnamespace={ns_used or ''}\n")


def dump_logs(api, job_id, ns, tail=None):
    n = 0
    try:
        for line in api.fetch_job_logs(job_id=job_id, namespace=ns, follow=False, tail=tail):
            print(line, flush=True); n += 1
    except Exception as e:  # noqa: BLE001
        print(f"[could not fetch the job log: {str(e)[:200]}]")
    return n


def cmd_wait(a):
    """Poll until the job leaves the queue, stream its log while it runs, and ALWAYS print the complete log at the
    end (the first run streamed nothing: follow=True returned at once while the job was still SCHEDULING)."""
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ.get("HF_TOKEN"))
    ns = a.namespace or None
    last = None; streamed = 0
    while True:
        info = api.inspect_job(job_id=a.job, namespace=ns)
        stage = info.status.stage
        if stage != last:
            print(f"[{time.strftime('%H:%M:%S')}] status {stage} {info.status.message or ''}", flush=True); last = stage
        if stage in TERMINAL:
            break
        if stage == "RUNNING" and not streamed:
            try:
                for line in api.fetch_job_logs(job_id=a.job, namespace=ns, follow=True):
                    print(line, flush=True); streamed += 1
            except Exception as e:  # noqa: BLE001
                print(f"[log stream ended: {str(e)[:200]}]")
            continue
        time.sleep(30)
    print(f"===== complete job log ({a.job}) =====", flush=True)
    dump_logs(api, a.job, ns)
    print("===== end of job log =====", flush=True)
    rec = json.loads(Path(a.record).read_text()) if Path(a.record).exists() else {}
    started = getattr(info, "created_at", None)
    minutes = round((time.time() - started.timestamp()) / 60, 1) if started else None
    rate = rec.get("rate_usd_per_hour") or RATES_USD_PER_HOUR.get(rec.get("flavor", ""), 0)
    bill = {"final_status": stage, "message": info.status.message, "minutes_since_submit": minutes,
            "note": "HF bills RUNNING time only; the queue wait is free — see the status timestamps above",
            "usd_upper_bound": round((minutes or 0) / 60 * rate, 2), "inr_upper_bound": round((minutes or 0) / 60 * rate * INR_PER_USD)}
    rec.update(bill); Path(a.record).write_text(json.dumps(rec, indent=1), encoding="utf-8")
    print(json.dumps(bill, indent=1))
    return 0 if stage == "COMPLETED" else 1


def cmd_logs(a):
    from huggingface_hub import HfApi
    api = HfApi(token=os.environ.get("HF_TOKEN"))
    ns = a.namespace or None
    info = api.inspect_job(job_id=a.job, namespace=ns)
    print(json.dumps({"id": info.id, "status": info.status.stage, "message": info.status.message, "flavor": str(info.flavor),
                      "created_at": str(getattr(info, "created_at", "")), "url": info.url}, indent=1))
    print(f"===== job log ({a.job}) =====")
    n = dump_logs(api, a.job, ns, tail=a.tail)
    print(f"===== {n} lines =====")


def cmd_collect(a):
    from huggingface_hub import snapshot_download
    p = snapshot_download(a.results_repo, token=os.environ.get("HF_TOKEN"), local_dir=a.out,
                          allow_patterns=["eval/**", "export/*.json", "export/*.md", "export/vocab.txt", "train.log"])
    print("collected →", p)
    ev = Path(a.out) / "eval/eval.json"
    if ev.exists():
        print(json.dumps(json.load(open(ev))["summary"], indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("--flavor", default="l4x1", choices=list(RATES_USD_PER_HOUR))
    s.add_argument("--timeout-minutes", type=int, default=150); s.add_argument("--train-cap-minutes", type=int, default=100)
    s.add_argument("--cap-inr", type=int, default=185); s.add_argument("--commit", required=True)
    s.add_argument("--namespace", default="SarvamulaOrg"); s.add_argument("--results-repo", default="SarvamulaOrg/kamadhenu-voice-a")
    s.add_argument("--name", default="kamadhenu-experiment-a"); s.add_argument("--record", default="experiment_a_job.json")
    s.add_argument("--precision", default="bf16", choices=["bf16", "fp16", "no"])
    s.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    w = sub.add_parser("wait"); w.add_argument("--job", required=True); w.add_argument("--namespace", default="SarvamulaOrg")
    w.add_argument("--record", default="experiment_a_job.json")
    c = sub.add_parser("collect"); c.add_argument("--results-repo", default="SarvamulaOrg/kamadhenu-voice-a"); c.add_argument("--out", default="out")
    l = sub.add_parser("logs"); l.add_argument("--job", required=True); l.add_argument("--namespace", default="SarvamulaOrg"); l.add_argument("--tail", type=int, default=None)
    a = ap.parse_args(argv)
    return {"submit": cmd_submit, "wait": cmd_wait, "collect": cmd_collect, "logs": cmd_logs}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main() or 0)
