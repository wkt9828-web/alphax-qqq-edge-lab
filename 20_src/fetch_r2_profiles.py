"""
fetch_r2_profiles.py -- READ-ONLY download of the Flywheel volume-profile files (QQQ, SPXW) from R2, for the v3 screen.
Run on Windows (Lara). Writes ONLY inside 10_data/r2_snapshot/profiles/. Computes nothing and looks at no returns: it only copies files
and records a provenance manifest (key, size, R2 LastModified, SHA-256).

  python 20_src\\fetch_r2_profiles.py --env C:\\Flywheel\\.env
Resumable: files already present with the same size are skipped. Credentials are read from the .env file and never printed.
"""
import argparse, hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import boto3, pandas as pd
from botocore.config import Config

ap = argparse.ArgumentParser()
ap.add_argument("--env", default=r"C:\Flywheel\.env")
ap.add_argument("--symbols", default="QQQ,SPXW")
ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "10_data" / "r2_snapshot"))
ap.add_argument("--workers", type=int, default=8)
a = ap.parse_args()
OUT = Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
env = {}
for l in open(a.env, encoding="utf-8-sig"):
    l = l.strip()
    if l and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
ep = env["R2_ACCOUNT_ID"] if env["R2_ACCOUNT_ID"].startswith("https://") else f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
s3 = boto3.client("s3", endpoint_url=ep, aws_access_key_id=env["R2_ACCESS_KEY_ID"], aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
                  region_name="auto", config=Config(signature_version="s3v4", retries={"max_attempts": 5}, max_pool_connections=a.workers * 2))
B = "flywheel-data"
objs = []
for sym in a.symbols.split(","):
    for p in s3.get_paginator("list_objects_v2").paginate(Bucket=B, Prefix=f"profiles/{sym}/"):
        for o in p.get("Contents", []):
            if o["Key"].endswith((".json", ".parquet")): objs.append(o)
print("files to fetch:", len(objs))

def get(o):
    dest = OUT / o["Key"]; dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size != o["Size"]:
        s3.download_file(B, o["Key"], str(dest))
    return dict(key=o["Key"], size=o["Size"], r2_last_modified=o["LastModified"].isoformat(), sha256=hashlib.sha256(dest.read_bytes()).hexdigest())

rows = []
with ThreadPoolExecutor(a.workers) as ex:
    for i, r in enumerate(ex.map(get, objs), 1):
        rows.append(r)
        if i % 500 == 0: print(i, "/", len(objs))
M = pd.DataFrame(rows).sort_values("key"); M.to_csv(OUT / "profiles_MANIFEST_R2.csv", index=False)
print("done:", len(M), "files |", round(M["size"].sum() / 1e6, 1), "MB | manifest:", OUT / "profiles_MANIFEST_R2.csv")
print("R2 LastModified range:", M["r2_last_modified"].min(), "->", M["r2_last_modified"].max())
