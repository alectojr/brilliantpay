#!/usr/bin/env python3
"""Back up the Render PostgreSQL database and receipt uploads to Cloudflare R2."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import boto3
import requests
from botocore.config import Config


def required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set.")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pg_dump_url(url: str) -> str:
    scheme, separator, remainder = url.partition("://")
    if not separator or scheme not in {
        "postgres",
        "postgresql",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }:
        raise RuntimeError("RENDER_DATABASE_URL must be a PostgreSQL connection URL.")
    return f"postgresql://{remainder}"


def download_upload_archive(url: str, token: str, destination: Path) -> None:
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise RuntimeError("RENDER_UPLOADS_BACKUP_URL must be an HTTPS URL.")

    with requests.post(
        url,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=(15, 600),
        allow_redirects=False,
    ) as response:
        response.raise_for_status()
        if response.headers.get("Content-Type", "").split(";", 1)[0] != "application/zip":
            raise RuntimeError("The uploads backup endpoint did not return a ZIP archive.")
        with destination.open("wb") as archive:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    archive.write(chunk)

    if destination.stat().st_size == 0:
        raise RuntimeError("The uploads backup archive is empty.")


def upload_and_verify(client, bucket: str, key: str, path: Path) -> dict[str, object]:
    size = path.stat().st_size
    digest = sha256_file(path)
    client.upload_file(
        str(path),
        bucket,
        key,
        ExtraArgs={"ContentType": "application/octet-stream"},
    )
    saved_object = client.head_object(Bucket=bucket, Key=key)
    if saved_object["ContentLength"] != size:
        raise RuntimeError(f"Uploaded object size verification failed for {key}.")
    return {"key": key, "size_bytes": size, "sha256": digest}


def main() -> None:
    database_url = required_environment("RENDER_DATABASE_URL")
    uploads_backup_url = required_environment("RENDER_UPLOADS_BACKUP_URL")
    backup_token = required_environment("BRILLIANTPAY_BACKUP_TOKEN")
    endpoint_url = required_environment("R2_ENDPOINT_URL")
    bucket = required_environment("R2_BUCKET")
    access_key = required_environment("R2_ACCESS_KEY_ID")
    secret_key = required_environment("R2_SECRET_ACCESS_KEY")

    if len(backup_token) < 32:
        raise RuntimeError("BRILLIANTPAY_BACKUP_TOKEN must be at least 32 characters.")
    database_url = pg_dump_url(database_url)
    if urlparse(endpoint_url).scheme != "https":
        raise RuntimeError("R2_ENDPOINT_URL must use HTTPS.")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"weekly/{timestamp[:4]}/{timestamp[4:6]}/brilliantpay-{timestamp}"
    database_key = f"{prefix}-database.dump"
    uploads_key = f"{prefix}-uploads.zip"
    manifest_key = f"{prefix}-manifest.json"

    with tempfile.TemporaryDirectory(prefix="brilliantpay-backup-") as directory:
        temp_directory = Path(directory)
        database_path = temp_directory / "database.dump"
        uploads_path = temp_directory / "uploads.zip"

        dump = subprocess.run(
            [
                "pg_dump",
                "--no-password",
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(database_path),
                database_url,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if dump.returncode:
            diagnostic = dump.stderr.strip()[:2000]
            raise RuntimeError(
                f"pg_dump failed with exit code {dump.returncode}: {diagnostic}"
            )
        if not database_path.is_file() or database_path.stat().st_size == 0:
            raise RuntimeError("pg_dump completed without creating a database archive.")

        download_upload_archive(uploads_backup_url, backup_token, uploads_path)

        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name="auto",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )
        objects = [
            upload_and_verify(client, bucket, database_key, database_path),
            upload_and_verify(client, bucket, uploads_key, uploads_path),
        ]
        manifest_path = temp_directory / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "database_format": "PostgreSQL custom dump",
                    "uploads_format": "ZIP archive",
                    "objects": objects,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        upload_and_verify(client, bucket, manifest_key, manifest_path)

    print(f"Verified weekly backup in R2 bucket {bucket}: {prefix}")


if __name__ == "__main__":
    main()
