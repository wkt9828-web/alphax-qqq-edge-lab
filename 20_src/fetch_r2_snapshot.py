"""
fetch_r2_snapshot.py  --  READ-ONLY snapshot of the Flywheel R2 files needed for the
Alpha X intraday project. Run on Windows (Lara). Writes ONLY inside 10_data/r2_snapshot.

  python fetch_r2_snapshot.py --env C:\\Flywheel\\.env
Credentials are read from the .env file; nothing secret is printed or copied.
Produces a MANIFEST_R2.csv (key, size, R2 LastModified, SHA-256, last data date) = provenance record.
"""
import argparse, hashlib, io, sys
from pathlib import Path
import boto3, pandas as pd
from botocore.config import Config

ap = argparse.ArgumentParser()
ap.add_argument("--env", default=r"C:\Flywheel\.env")
ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "10_data" / "r2_snapshot"))
a = ap.parse_args()
OUT = Path(a.out); OUT.mkdir(parents=True, exist_ok=True)

env = {}
for l in open(a.env, encoding="utf-8-sig"):
    l = l.strip()
    if l and not l.startswith("#") and "=" in l:
        k, v = l.split("=", 1); env[k.strip()] = v.strip().strip('"').strip("'")
ep = env["R2_ACCOUNT_ID"] if env["R2_ACCOUNT_ID"].startswith("https://") else f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
s3 = boto3.client("s3", endpoint_url=ep, aws_access_key_id=env["R2_ACCESS_KEY_ID"],
                  aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"], region_name="auto",
                  config=Config(signature_version="s3v4", retries={"max_attempts": 4}))
B = "flywheel-data"

FILES = [
 "market_data/daily/QQQ.csv", "market_data/daily/IWM.csv", "market_data/daily/_GSPC.csv",
 "market_data/daily/_VIX.csv", "market_data/daily/_VIX3M.csv",
 "market_data/fred/observations/BAMLH0A0HYM2.parquet", "market_data/fred/observations/BAMLC0A0CM.parquet",
 "market_data/fred/observations/DGS10.parquet", "market_data/fred/observations/DGS2.parquet",
 "news/economic_calendar.csv", "options/option_volume_index.csv",
 "flywheel_data/uw/realized_vol_trailing.csv", "flywheel_data/derived/realized_vol.csv",
]
rows = []
def last_date(path, key):
    try:
        df = pd.read_parquet(path) if key.endswith(".parquet") else pd.read_csv(path)
        c = [x for x in df.columns if x.lower() in ("date", "datetime")]
        return str(pd.to_datetime(df[c[0]], errors="coerce").max().date()) if c else ""
    except Exception as e:
        return "ERR:" + type(e).__name__

def get(key):
    dest = OUT / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = s3.head_object(Bucket=B, Key=key)
    if not dest.exists() or dest.stat().st_size != h["ContentLength"]:
        s3.download_file(B, key, str(dest))
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    rows.append(dict(key=key, size=h["ContentLength"], r2_last_modified=h["LastModified"].isoformat(),
                     sha256=sha, last_data_date=last_date(dest, key) if not key.endswith("_gex_table.csv") else ""))

for k in FILES:
    get(k); print("ok", k)

# GEX tables for QQQ and IWM (all snapshots; ~1,440 small files)
for t in ("QQQ", "IWM"):
    n = 0
    for p in s3.get_paginator("list_objects_v2").paginate(Bucket=B, Prefix=f"historical_gex/{t}/"):
        for o in p.get("Contents", []):
            if o["Key"].endswith("_gex_table.csv"):
                get(o["Key"]); n += 1
    print("GEX", t, n, "files")

pd.DataFrame(rows).to_csv(OUT / "MANIFEST_R2.csv", index=False)
print("Done. Manifest:", OUT / "MANIFEST_R2.csv")
