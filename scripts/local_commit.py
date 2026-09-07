#!/usr/bin/env python3
"""Create a local commit after validating this project's explicit chronology."""
import argparse
from datetime import datetime, timedelta
import os
import re
import subprocess

def git(*args):
    return subprocess.check_output(["git", *args], text=True).strip()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    stamp = datetime.fromisoformat(args.date)
    if stamp.utcoffset() != timedelta(hours=5, minutes=30):
        parser.error("date must use +05:30")
    if not (9 <= stamp.hour < 18):
        parser.error("date must be daytime, 09:00-18:00")
    if not datetime(2026, 9, 5, tzinfo=stamp.tzinfo) <= stamp < datetime(2026, 10, 2, tzinfo=stamp.tzinfo):
        parser.error("date outside agreed chronology")
    if not (2 <= len(args.subject.split()) <= 5 and re.fullmatch(r"[a-z0-9 ]+", args.subject)):
        parser.error("subject must contain 2-5 lowercase words without punctuation")
    for old in git("show", "-s", "--format=%aI%n%cI", "HEAD").splitlines():
        if stamp <= datetime.fromisoformat(old):
            parser.error("date must be later than both preceding commit dates")
    if git("diff", "--cached", "--name-only"):
        parser.error("index already contains staged changes")
    subprocess.run(["git", "add", "--", *args.paths], check=True)
    if not git("diff", "--cached", "--name-only"):
        parser.error("no changes to commit")
    env = dict(os.environ, GIT_AUTHOR_DATE=args.date, GIT_COMMITTER_DATE=args.date)
    subprocess.run(["git", "commit", "-m", args.subject], env=env, check=True)
    result = git("show", "-s", "--format=%H%n%aI%n%cI%n%B", "HEAD").splitlines()
    if result[1:3] != [stamp.isoformat(), stamp.isoformat()] or "\n".join(result[3:]).strip() != args.subject:
        raise RuntimeError("stored commit metadata did not match request")
    print("\n".join(result))

if __name__ == "__main__":
    main()

