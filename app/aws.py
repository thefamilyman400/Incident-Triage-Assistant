"""
aws.py — AWS integration helpers for S3 document storage and Secrets Manager.

Environment variables (set in .env or injected via ECS/Lightsail):
  AWS_REGION          — e.g. us-east-1  (required)
  S3_BUCKET_NAME      — bucket holding runbooks/, incidents/, docs/  (required for S3)
  SECRETS_MANAGER_ARN — full ARN or secret name in Secrets Manager  (optional)

If SECRETS_MANAGER_ARN is not set, the app falls back to reading API keys
from the local .env file exactly as before — so this is fully backwards-compatible.
If S3_BUCKET_NAME is not set, document loading falls back to local disk.
"""
import os
import json
import logging
from typing import List, Optional

log = logging.getLogger(__name__)

# ── lazy boto3 import — only fails if AWS integration is actually used ──
def _boto3():
    try:
        import boto3
        return boto3
    except ImportError:
        raise ImportError("boto3 is not installed. Run: pip install boto3>=1.34.0")


# ═══════════════════════════════════════════════════════════════
# Secrets Manager
# ═══════════════════════════════════════════════════════════════

def load_secrets() -> dict:
    """
    Fetch API keys from AWS Secrets Manager.

    The secret must be a JSON object with at minimum:
      { "GOOGLE_API_KEY": "...", "GROQ_API_KEY": "..." }

    Optional keys also pulled if present:
      GOOGLE_GEMINI_MODEL, GROQ_MODEL

    Returns a dict of key→value. If SECRETS_MANAGER_ARN is not configured,
    returns an empty dict (caller falls back to os.getenv).
    """
    secret_id = os.getenv("SECRETS_MANAGER_ARN", "")
    if not secret_id:
        log.debug("SECRETS_MANAGER_ARN not set — skipping Secrets Manager.")
        return {}

    region = os.getenv("AWS_REGION", "us-east-1")
    boto3 = _boto3()

    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=secret_id)
        secret_str = response.get("SecretString", "{}")
        secrets = json.loads(secret_str)
        print(f"[AWS] Loaded {len(secrets)} keys from Secrets Manager ({secret_id}).")
        return secrets
    except Exception as e:
        print(f"[AWS] WARNING: Secrets Manager fetch failed — {e}")
        print(f"[AWS] Falling back to .env / environment variables.")
        return {}


def get_api_keys() -> dict:
    """
    Return API key config, preferring Secrets Manager over .env.

    Usage in main.py:
        from aws import get_api_keys
        keys = get_api_keys()
        GOOGLE_API_KEY = keys["GOOGLE_API_KEY"]
    """
    secrets = load_secrets()

    return {
        "GOOGLE_API_KEY":      secrets.get("GOOGLE_API_KEY")      or os.getenv("GOOGLE_API_KEY", ""),
        "GOOGLE_GEMINI_MODEL": secrets.get("GOOGLE_GEMINI_MODEL") or os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.5-flash"),
        "GROQ_API_KEY":        secrets.get("GROQ_API_KEY")        or os.getenv("GROQ_API_KEY", ""),
        "GROQ_MODEL":          secrets.get("GROQ_MODEL")          or os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
    }


# ═══════════════════════════════════════════════════════════════
# S3 Document Loading
# ═══════════════════════════════════════════════════════════════

DOCS_PREFIXES = ["runbooks", "incidents", "docs"]   # S3 key prefixes (= folder names)


def s3_load_documents() -> Optional[List[dict]]:
    """
    Load all .md files from the S3 bucket under runbooks/, incidents/, docs/.

    Returns a list of document dicts (same schema as the local loader):
      { "source": "runbooks/HIGH_CPU.md", "content": "...", "folder": "runbooks" }

    Returns None if S3_BUCKET_NAME is not configured (triggers local fallback).
    """
    bucket = os.getenv("S3_BUCKET_NAME", "")
    if not bucket:
        log.debug("S3_BUCKET_NAME not set — skipping S3 document load.")
        return None

    region = os.getenv("AWS_REGION", "us-east-1")
    boto3 = _boto3()
    s3 = boto3.client("s3", region_name=region)

    docs = []
    try:
        for prefix in DOCS_PREFIXES:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix}/"):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if not key.endswith((".md", ".txt")):
                        continue
                    try:
                        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
                        docs.append({
                            "source": key,
                            "content": body,
                            "folder": prefix,
                        })
                        log.debug("Loaded s3://%s/%s", bucket, key)
                    except Exception as e:
                        log.warning("Skipping s3://%s/%s — %s", bucket, key, e)
    except Exception as e:
        print(f"[AWS] WARNING: S3 document load failed — {e}")
        print(f"[AWS] Falling back to local disk documents.")
        return None

    print(f"[AWS] Loaded {len(docs)} documents from s3://{bucket}")
    return docs


def s3_upload_document(filename: str, content: bytes, folder: str = "runbooks") -> str:
    """
    Upload a document to S3 under the given folder prefix.

    Returns the S3 key (e.g. "runbooks/MY_RUNBOOK.md").
    Raises RuntimeError if S3_BUCKET_NAME is not configured.
    """
    bucket = os.getenv("S3_BUCKET_NAME", "")
    if not bucket:
        raise RuntimeError("S3_BUCKET_NAME is not set — cannot upload to S3.")

    region = os.getenv("AWS_REGION", "us-east-1")
    boto3 = _boto3()
    s3 = boto3.client("s3", region_name=region)

    key = f"{folder}/{filename}"
    s3.put_object(Bucket=bucket, Key=key, Body=content, ContentType="text/markdown")
    log.info("Uploaded s3://%s/%s", bucket, key)
    return key


def s3_list_document_keys() -> List[str]:
    """Return all S3 keys currently in the knowledge base bucket."""
    bucket = os.getenv("S3_BUCKET_NAME", "")
    if not bucket:
        return []

    region = os.getenv("AWS_REGION", "us-east-1")
    boto3 = _boto3()
    s3 = boto3.client("s3", region_name=region)

    keys = []
    for prefix in DOCS_PREFIXES:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=f"{prefix}/"):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith((".md", ".txt")):
                    keys.append(obj["Key"])
    return keys
