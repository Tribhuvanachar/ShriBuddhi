#!/usr/bin/env python3
"""Run record + results publishing for launch_experiment_a.sh (kept out of the shell script for readability).

    run_record.py --out run.json --vram 24GB --batch 3200 --epochs 34 --cap 100 --rc 0 --step 3060 --t T0 T1 T2 T3
    run_record.py --publish <org>/<repo> --export DIR --eval DIR --log FILE      # private Hub repo, HF_TOKEN from env
"""
import argparse, json, os, sys, time


def gpu_name():
    try:
        d = "/proc/driver/nvidia/gpus"
        return open(os.path.join(d, os.listdir(d)[0], "information")).read().split("\n")[0]
    except Exception:  # noqa: BLE001
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out"); ap.add_argument("--vram"); ap.add_argument("--batch"); ap.add_argument("--epochs"); ap.add_argument("--cap")
    ap.add_argument("--rc"); ap.add_argument("--step"); ap.add_argument("--t", nargs=4, type=int)
    ap.add_argument("--publish"); ap.add_argument("--export"); ap.add_argument("--eval"); ap.add_argument("--log")
    a = ap.parse_args(argv)
    if a.out:
        t0, t1, t2, t3 = a.t
        rec = {"finished_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "vram": a.vram, "batch_frames": int(a.batch),
               "epochs": int(a.epochs), "train_cap_minutes": int(a.cap), "train_exit_code": int(a.rc), "last_step": a.step,
               "minutes": {"setup": round((t1 - t0) / 60, 1), "train": round((t2 - t1) / 60, 1),
                           "export_eval": round((t3 - t2) / 60, 1), "total": round((t3 - t0) / 60, 1)}, "gpu": gpu_name()}
        json.dump(rec, open(a.out, "w"), indent=1); print(json.dumps(rec, indent=1))
    if a.publish:
        from huggingface_hub import HfApi
        api = HfApi(token=os.environ["HF_TOKEN"])
        api.create_repo(a.publish, repo_type="model", private=True, exist_ok=True)
        api.upload_folder(repo_id=a.publish, folder_path=a.export, path_in_repo="export", commit_message="Experiment A export")
        api.upload_folder(repo_id=a.publish, folder_path=a.eval, path_in_repo="eval", commit_message="Experiment A A/B renders")
        api.upload_file(repo_id=a.publish, path_or_fileobj=a.log, path_in_repo="train.log", commit_message="Experiment A train log")
        print("results →", f"https://huggingface.co/{a.publish}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
