# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests",
#   "types-requests"
# ]
# ///
# Fetches dbt Cloud run status, step logs, and artifacts.
#
# Accepts either a dbt Cloud run URL or environment variables.
# Only DBT_PAT is required when passing a URL.
#
# Usage:
#   # From a URL (recommended — copy-paste from dbt Cloud browser)
#   dbt_cloud_run.sh https://<host>/deploy/<account>/projects/<project>/runs/<run_id>/
#   dbt_cloud_run.sh <URL> --errors-only
#
#   # Pipe from gh cli — extract the dbt Cloud check URL from the current PR
#   dbt_cloud_run.sh "$(gh pr checks --json link \
#     --jq '.[] | select(.link | test("dbt.com.*/runs/")) | .link' | head -1)"
#
#   # From environment variables
#   export DBT_ACCOUNT_ID=<account> DBT_PROJECT_ID=<project> DBT_RUN_ID=<run_id>
#   dbt_cloud_run.sh

import os
import re
import sys
import json
import argparse
import logging
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

RUN_STATUS_MAP = {
    1: "Queued",
    2: "Starting",
    3: "Running",
    10: "Success",
    20: "Error",
    30: "Cancelled",
}

# Pattern: https://{ui_host}/deploy/{account_id}/projects/{project_id}/runs/{run_id}/
_URL_PATTERN = re.compile(
    r"https?://(?P<ui_host>[^/]+)/deploy/(?P<account_id>\d+)/projects/(?P<project_id>\d+)/runs/(?P<run_id>\d+)"
)


@dataclass
class Config:
    api_base: str
    api_key: str
    account_id: str
    project_id: str
    run_id: str
    ui_host: str

    @property
    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}

    @property
    def run_url(self) -> str:
        return f"https://{self.ui_host}/deploy/{self.account_id}/projects/{self.project_id}/runs/{self.run_id}/"

    @classmethod
    def from_url(cls, url: str) -> "Config":
        """Parse a dbt Cloud run URL to extract IDs."""
        m = _URL_PATTERN.match(url)
        if not m:
            raise ValueError(f"Cannot parse dbt Cloud URL: {url}")
        return cls(
            api_base=os.environ.get("DBT_CLOUD_HOST", "cloud.getdbt.com"),
            api_key=os.environ["DBT_PAT"],
            account_id=m.group("account_id"),
            project_id=m.group("project_id"),
            run_id=m.group("run_id"),
            ui_host=m.group("ui_host"),
        )

    @classmethod
    def from_env(cls) -> "Config":
        """Build config from environment variables."""
        api_base = os.getenv("DBT_CLOUD_HOST", "au.dbt.com")
        return cls(
            api_base=api_base,
            api_key=os.environ["DBT_PAT"],
            account_id=os.environ["DBT_ACCOUNT_ID"],
            project_id=os.getenv("DBT_PROJECT_ID", ""),
            run_id=os.environ["DBT_RUN_ID"],
            ui_host=os.getenv("DBT_CLOUD_UI_HOST", f"cs441.{api_base}"),
        )


# ------------------------------------------------------------------------------
# API
# ------------------------------------------------------------------------------


def api_get(cfg: Config, path: str, params: dict | None = None) -> dict:
    url = f"https://{cfg.api_base}/api/v2/accounts/{cfg.account_id}/{path}"
    log.debug(f"GET {url}")
    resp = requests.get(url, headers=cfg.auth_header, params=params)
    resp.raise_for_status()
    return resp.json()


def get_run(cfg: Config, *, include_steps: bool = False) -> dict:
    params = {"include_related": "run_steps"} if include_steps else None
    return api_get(cfg, f"runs/{cfg.run_id}/", params)


def get_artifact(cfg: Config, artifact_path: str) -> dict:
    return api_get(cfg, f"runs/{cfg.run_id}/artifacts/{artifact_path}")


def list_artifacts(cfg: Config) -> list[str]:
    data = api_get(cfg, f"runs/{cfg.run_id}/artifacts/")
    return data.get("data", [])


# ------------------------------------------------------------------------------
# Display
# ------------------------------------------------------------------------------


def print_run_summary(cfg: Config, run_data: dict) -> None:
    d = run_data["data"]
    status = RUN_STATUS_MAP.get(d["status"], f"Unknown({d['status']})")
    print(f"Run:      {d['id']}")
    print(f"Status:   {status}")
    print(f"Job:      {d.get('job_id', 'N/A')}")
    print(f"Project:  {d.get('project_id', 'N/A')}")
    print(f"Branch:   {d.get('git_branch') or d.get('git_sha') or 'N/A'}")
    print(f"Started:  {d.get('started_at', 'N/A')}")
    print(f"Finished: {d.get('finished_at', 'N/A')}")
    print(f"URL:      {cfg.run_url}")
    print()


def print_steps(run_data: dict, step_filter: int | None = None) -> None:
    steps = run_data["data"].get("run_steps", [])
    if not steps:
        print("No run steps found.")
        return
    for s in steps:
        if step_filter is not None and s["index"] != step_filter:
            continue
        status = s["status_humanized"]
        marker = "  " if status == "Success" else ">>"
        print(f"{marker} Step {s['index']}: {s['name']} — {status} ({s.get('duration_humanized', '?')})")
        if status not in ("Success", "Skipped"):
            logs = s.get("logs", "") or ""
            for line in logs.split("\n"):
                stripped = line.strip()
                if any(kw in stripped for kw in ["FAIL", "ERROR", "Error", "Failure", "Database Error"]):
                    print(f"     {stripped}")
            print()


def print_errors_from_steps(run_data: dict) -> None:
    steps = run_data["data"].get("run_steps", [])
    found_errors = False
    for s in steps:
        if s["status_humanized"] not in ("Error", "Failed"):
            continue
        logs = s.get("logs", "") or ""
        lines = logs.split("\n")
        i = 0
        while i < len(lines):
            if "Failure in model" in lines[i] or "Failure in test" in lines[i]:
                found_errors = True
                while i < len(lines):
                    print(lines[i].strip())
                    i += 1
                    if i < len(lines) and lines[i].strip() == "":
                        print()
                        break
            i += 1
    if not found_errors:
        for s in steps:
            if s["status_humanized"] not in ("Error", "Failed"):
                continue
            logs = s.get("logs", "") or ""
            for line in logs.split("\n"):
                stripped = line.strip()
                if any(kw in stripped for kw in ["ERROR", "Error", "FAIL "]):
                    print(stripped)


def print_run_results_summary(cfg: Config) -> None:
    try:
        data = get_artifact(cfg, "run_results.json")
    except requests.exceptions.HTTPError:
        print("run_results.json not available for this run.")
        return
    results = data.get("results", [])
    if not results:
        print("No results in run_results.json (may be from a non-build step).")
        return
    from collections import Counter
    statuses = Counter(r.get("status", "unknown") for r in results)
    print(f"Results: {dict(statuses)}")
    print()
    for r in results:
        status = r.get("status", "")
        if status in ("error", "fail"):
            print(f"  {status.upper()}: {r.get('unique_id', 'unknown')}")
            print(f"    {r.get('message', '')[:300]}")
            print()


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch dbt Cloud run status and artifacts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dbt_cloud_run.sh https://<host>/deploy/<acct>/projects/<proj>/runs/<run_id>/
  dbt_cloud_run.sh <URL> --errors-only
  dbt_cloud_run.sh <URL> --step 6
  dbt_cloud_run.sh "$(gh pr checks --json link \\
    --jq '.[] | select(.link | test("dbt.com.*/runs/")) | .link' | head -1)"

Environment variables:
  DBT_PAT              Personal access token (required)
  DBT_CLOUD_HOST       API host (e.g. us.dbt.com, au.dbt.com, emea.dbt.com)
  DBT_ACCOUNT_ID       Account ID (or pass URL)
  DBT_PROJECT_ID       Project ID (or pass URL)
  DBT_RUN_ID           Run ID (or pass URL)
""",
    )
    parser.add_argument("url", nargs="?", default=None, help="dbt Cloud run URL")
    parser.add_argument("--errors-only", action="store_true", help="Show only error/failure details")
    parser.add_argument("--step", type=int, default=None, help="Show logs for a specific step number")
    parser.add_argument("--artifact", type=str, default=None, help="Fetch and print a specific artifact")
    parser.add_argument("--list-artifacts", action="store_true", help="List available artifacts")
    parser.add_argument("--results", action="store_true", help="Show run_results.json summary")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    cfg = Config.from_url(args.url) if args.url else Config.from_env()

    if args.list_artifacts:
        for a in list_artifacts(cfg):
            print(a)
        return
    if args.artifact:
        print(json.dumps(get_artifact(cfg, args.artifact), indent=2))
        return

    run_data = get_run(cfg, include_steps=True)

    if args.errors_only:
        print_errors_from_steps(run_data)
        return
    if args.results:
        print_run_results_summary(cfg)
        return

    print_run_summary(cfg, run_data)
    print_steps(run_data, step_filter=args.step)


if __name__ == "__main__":
    log_level = logging.DEBUG if os.getenv("LOG_LEVEL") == "DEBUG" else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        main()
    except KeyError as e:
        log.error(f"Missing required environment variable: {e}")
        sys.exit(1)
    except ValueError as e:
        log.error(str(e))
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        log.error(f"API error: {e}")
        sys.exit(1)
