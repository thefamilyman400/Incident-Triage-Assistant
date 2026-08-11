#!/usr/bin/env python3
"""
scripts/s3_sync.py — One-time upload of all local runbooks/incidents/docs to S3.

Run this ONCE after creating your S3 bucket to seed it with your existing knowledge base.

Usage:
    # From the project root:
    python scripts/s3_sync.py

Required env vars (set in .env or export before running):
    AWS_REGION       — e.g. us-east-1
    S3_BUCKET_NAME   — the bucket you created for documents

Optional:
    DRY_RUN=1        — print what would be uploaded without actually uploading
"""
import os
import sys
import glob
from pathlib import Path

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "app" / ".env")

DOCS_DIRS   = ["runbooks", "incidents", "docs"]
DRY_RUN     = os.getenv("DRY_RUN", "0") == "1"
BUCKET      = os.getenv("S3_BUCKET_NAME", "")
REGION      = os.getenv("AWS_REGION", "us-east-1")
PROJECT_ROOT = Path(__file__).parent.parent


def main():
    if not BUCKET:
        print("ERROR: S3_BUCKET_NAME is not set.")
        print("  export S3_BUCKET_NAME=your-bucket-name")
        sys.exit(1)

    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3>=1.34.0")
        sys.exit(1)

    s3 = boto3.client("s3", region_name=REGION)

    uploaded = 0
    skipped  = 0

    for folder in DOCS_DIRS:
        folder_path = PROJECT_ROOT / folder
        if not folder_path.exists():
            print(f"  [skip] {folder}/ — directory not found locally")
            continue

        for filepath in sorted(folder_path.glob("*.md")) + sorted(folder_path.glob("*.txt")):
            s3_key = f"{folder}/{filepath.name}"

            if DRY_RUN:
                print(f"  [dry-run] would upload → s3://{BUCKET}/{s3_key}")
                uploaded += 1
                continue

            try:
                with open(filepath, "rb") as f:
                    content = f.read()
                s3.put_object(
                    Bucket=BUCKET,
                    Key=s3_key,
                    Body=content,
                    ContentType="text/markdown",
                )
                print(f"  [ok] s3://{BUCKET}/{s3_key}  ({len(content):,} bytes)")
                uploaded += 1
            except Exception as e:
                print(f"  [error] {filepath.name} — {e}")
                skipped += 1

    print()
    if DRY_RUN:
        print(f"Dry run complete — {uploaded} files would be uploaded to s3://{BUCKET}")
    else:
        print(f"Sync complete — {uploaded} uploaded, {skipped} failed.")
        print(f"Set S3_BUCKET_NAME={BUCKET} in your .env (or Secrets Manager) and restart the app.")


if __name__ == "__main__":
    main()
