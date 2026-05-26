#!/usr/bin/env python3
"""
Gmail Cleaner - A tool to batch delete all emails from a Gmail account via Gmail API.

Usage:
    1. Enable Gmail API and download OAuth credentials from Google Cloud Console
    2. Save credentials as credentials.json in the same directory
    3. pip install -r requirements.txt
    4. python gmail_cleaner.py

The first run opens a browser for OAuth login. A token.pickle file caches
the session so subsequent runs skip re-authentication.
"""

import argparse
import os
import pickle
import sys
import time

import requests
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build as build_service

SCOPES = ["https://mail.google.com/"]
MAX_BATCH_SIZE = 1000

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CREDENTIALS = os.path.join(BASE_DIR, "credentials.json")
DEFAULT_TOKEN = os.path.join(BASE_DIR, "token.pickle")


class ProxiedHttp:
    """
    A requests-based HTTP transport compatible with googleapiclient.

    Supports SOCKS5/HTTP proxies via the requests library. This replaces
    httplib2 (which has proxy issues on some platforms) as the HTTP layer.
    """

    def __init__(self, credentials, proxy_url=None):
        self.credentials = credentials
        self.session = requests.Session()
        if proxy_url:
            self.session.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }

    def request(self, uri, method="GET", body=None, headers=None, **kwargs):
        headers = headers or {}
        self.credentials.apply(headers)
        headers.setdefault("user-agent", "gmail-cleaner/1.0")

        resp = self.session.request(
            method, uri, data=body, headers=headers, timeout=60, **kwargs
        )

        class Response:
            def __init__(self, r):
                self.status = r.status_code
                self.reason = r.reason
                for k, v in r.headers.items():
                    setattr(self, k, v)

            def __getitem__(self, key):
                return getattr(self, key)

        return Response(resp), resp.content


def authenticate(credentials_file, token_file, proxy=None):
    """Authenticate with OAuth and return a Gmail API service handle."""
    creds = None

    if os.path.exists(token_file):
        with open(token_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            session = requests.Session()
            if proxy:
                session.proxies = {"http": proxy, "https": proxy}
            creds.refresh(GoogleRequest(session=session))
        else:
            if not os.path.exists(credentials_file):
                print(f"ERROR: {credentials_file} not found.")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project and enable Gmail API")
                print("3. Create OAuth 2.0 Client ID (Desktop app)")
                print("4. Download JSON and save as credentials.json")
                sys.exit(1)

            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_file, "wb") as f:
            pickle.dump(creds, f)

    http = ProxiedHttp(creds, proxy_url=proxy)
    return build_service("gmail", "v1", http=http)


def get_message_count(service):
    """Return total message count for the authenticated mailbox."""
    profile = service.users().getProfile(userId="me").execute()
    return profile.get("messagesTotal", 0)


def iter_message_ids(service):
    """Yield every message ID in the mailbox (paginated)."""
    page_token = None
    while True:
        resp = (
            service.users().messages()
            .list(
                userId="me",
                maxResults=500,
                pageToken=page_token,
                fields="nextPageToken,messages/id",
            )
            .execute()
        )
        for msg in resp.get("messages", []):
            yield msg["id"]
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.1)


def batch_delete(service, msg_ids):
    """Permanently delete a batch of messages (max 1000)."""
    service.users().messages().batchDelete(
        userId="me", body={"ids": msg_ids}
    ).execute()


def run(credentials_file, token_file, proxy, dry_run=False, force=False):
    """Main entry point -- authenticate, count, confirm, delete."""
    print("Authenticating...")
    service = authenticate(credentials_file, token_file, proxy=proxy)

    total = get_message_count(service)
    print(f"Total messages in account: {total}")

    if total == 0:
        print("No messages to delete.")
        return

    if dry_run:
        print("[DRY RUN] Would delete all messages. Exiting.")
        return

    if not force:
        try:
            confirm = input(
                f"\nType YES to permanently delete ALL {total} messages: "
            )
        except EOFError:
            print(
                "\nInteractive input not available."
                " Use --force to skip confirmation."
            )
            sys.exit(1)

        if confirm != "YES":
            print("Aborted.")
            return

    print("\nFetching message IDs...")
    all_ids = list(iter_message_ids(service))
    print(f"Found {len(all_ids)} messages to delete.")

    deleted = 0
    for i in range(0, len(all_ids), MAX_BATCH_SIZE):
        batch = all_ids[i : i + MAX_BATCH_SIZE]
        for attempt in range(6):
            try:
                batch_delete(service, batch)
                deleted += len(batch)
                print(f"  Deleted {deleted}/{len(all_ids)} messages...")
                break
            except Exception as e:
                if attempt >= 5:
                    print(f"  ERROR after 5 retries: {e}")
                    break
                wait = 2**attempt
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)

    print(f"\nDone. Deleted {deleted} messages total.")


def main():
    parser = argparse.ArgumentParser(
        description="Batch delete all Gmail messages via Gmail API."
    )
    parser.add_argument(
        "--credentials",
        default=DEFAULT_CREDENTIALS,
        help="Path to OAuth credentials JSON (default: ./credentials.json)",
    )
    parser.add_argument(
        "--token",
        default=DEFAULT_TOKEN,
        help="Path to token pickle cache (default: ./token.pickle)",
    )
    parser.add_argument(
        "--proxy",
        default=None,
        help="HTTP/SOCKS5 proxy URL for API requests "
        "(e.g. http://127.0.0.1:7890)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show message count without deleting anything",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (useful for scripting)",
    )
    args = parser.parse_args()
    run(args.credentials, args.token, args.proxy, args.dry_run, args.force)


if __name__ == "__main__":
    main()
