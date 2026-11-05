import argparse
from contextlib import contextmanager
from functools import partial
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


VERSION = "1.1.1"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
BUCKET_PATTERN = re.compile(
    r"^(?P<prefix>db|rb)_"
    r"(?P<newest>\d+)_"
    r"(?P<oldest>\d+)_"
    r"(?P<bucket_id>[A-Za-z0-9][A-Za-z0-9.-]*(?:_[A-Za-z0-9][A-Za-z0-9.-]*)*)$"
)
INTEGRITY_PATTERN = re.compile(r"succeeded=(\d+),\s*failed=(\d+)")

Bucket = dict[str, int | str]
Runner = Callable[..., subprocess.CompletedProcess[str]]
JOURNALS = {"journal.zst", "journal.gz"}


def run_command(command: Sequence[str], *, timeout: float = 3600, **kwargs):
    """Bound external work and prevent interactive CLI prompts from hanging."""
    return subprocess.run(command, timeout=timeout, stdin=subprocess.DEVNULL, **kwargs)


def validate_index(index: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", index):
        raise ValueError(f"Invalid index name: {index!r}; expected a single safe name")


def eprint(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def parse_bucket_name(name: str) -> Bucket | None:
    """Parse db/rb bucket names, including suffixes with extra segments."""

    match = BUCKET_PATTERN.fullmatch(name)
    if not match:
        return None
    newest = int(match.group("newest"))
    oldest = int(match.group("oldest"))
    if newest < oldest:
        return None
    return {
        "name": name,
        "newest": newest,
        "oldest": oldest,
        "id": match.group("bucket_id"),
    }


def parse_datetime(value: str, timezone_name: str | None = None) -> int:
    try:
        parsed = datetime.strptime(value, DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(
            f"Invalid date {value!r}; expected format {DATE_FORMAT!r}"
        ) from exc

    if timezone_name:
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {timezone_name}") from exc
        candidates = {
            int(parsed.replace(tzinfo=timezone, fold=fold).timestamp())
            for fold in (0, 1)
            if datetime.fromtimestamp(
                parsed.replace(tzinfo=timezone, fold=fold).timestamp(), timezone
            ).replace(tzinfo=None) == parsed
        }
        if len(candidates) != 1:
            raise ValueError(
                f"Ambiguous or nonexistent local time {value!r} in {timezone_name}; "
                "specify the interval in UTC"
            )
        return candidates.pop()
    return int(time.mktime(parsed.timetuple()))


def handle_dates(
    oldest_time: str,
    newest_time: str,
    timezone_name: str | None = None,
) -> tuple[int, int]:
    """Convert the requested interval to epoch seconds and validate order."""

    oldest = parse_datetime(oldest_time, timezone_name)
    newest = parse_datetime(newest_time, timezone_name)
    if oldest > newest:
        raise ValueError("oldest_time must be earlier than or equal to newest_time")
    return oldest, newest


def format_epoch(epoch: int, timezone_name: str | None = None) -> str:
    if timezone_name:
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {timezone_name}") from exc
        return datetime.fromtimestamp(epoch, timezone).strftime(DATE_FORMAT)
    return time.strftime(DATE_FORMAT, time.localtime(epoch))


def find_buckets(
    source_path: str | os.PathLike[str],
    oldest_epoch_time: int,
    newest_epoch_time: int,
) -> list[str]:
    """Find bucket directories that overlap the requested interval."""

    source = Path(source_path).expanduser()
    if not source.exists():
        raise RuntimeError(f"Source path does not exist: {source}")
    if not source.is_dir():
        raise RuntimeError(f"Source path is not a directory: {source}")

    found: list[tuple[int, int, str]] = []
    with os.scandir(source) as entries:
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            bucket = parse_bucket_name(entry.name)
            if bucket is None:
                eprint(f"Warning: skipping invalid bucket directory: {entry.name}")
                continue
            if (
                int(bucket["newest"]) >= oldest_epoch_time
                and int(bucket["oldest"]) <= newest_epoch_time
            ):
                found.append(
                    (int(bucket["oldest"]), int(bucket["newest"]), entry.name)
                )

    found.sort()
    names = [item[2] for item in found]
    print(f"The number of bucket(s) found in the local path: {len(names)}.")
    return names


def bucket_date_range(buckets_found: Sequence[str]) -> tuple[int, int]:
    parsed = [parse_bucket_name(name) for name in buckets_found]
    buckets = [bucket for bucket in parsed if bucket is not None]
    if not buckets:
        raise RuntimeError("No valid buckets were found")
    oldest = min(int(bucket["oldest"]) for bucket in buckets)
    newest = max(int(bucket["newest"]) for bucket in buckets)
    return oldest, newest


def find_oldest_and_newest_bucket_dates(
    buckets_found: Sequence[str],
    source_path: str = "",
    index: str = "",
    timezone_name: str | None = None,
) -> tuple[int, int]:
    """Print and return the true outer date range of the supplied buckets."""

    oldest, newest = bucket_date_range(buckets_found)
    if not index and source_path:
        index = Path(source_path).expanduser().resolve().name
    print(f"For {index!r} index")
    print(
        f"Oldest date: {format_epoch(oldest, timezone_name)!r}, "
        f"newest date: {format_epoch(newest, timezone_name)!r}."
    )
    return oldest, newest


def _command_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part).strip()


def _failure_text(exc: BaseException) -> str:
    if isinstance(exc, subprocess.CalledProcessError):
        output = "\n".join(
            str(part) for part in (exc.stdout, exc.stderr) if part
        ).strip()
        return output or str(exc)
    return str(exc)


def list_s3_objects(
    bucket_name: str,
    index: str,
    endpoint: str = "",
    aws_binary: str = "aws",
    runner: Runner = run_command,
) -> list[dict[str, object]]:
    validate_index(index)
    command = [
        aws_binary,
        "s3api",
        "list-objects-v2",
        "--bucket",
        bucket_name,
        "--prefix",
        f"{index}/",
        "--query",
        "Contents[].{Key: Key, Size: Size, ETag: ETag}",
        "--output",
        "json",
    ]
    if endpoint:
        command.extend(["--endpoint-url", endpoint])
    try:
        result = runner(command, check=True, capture_output=True, text=True)
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"Unable to list S3 objects: {_failure_text(exc)}") from exc

    try:
        objects = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("AWS CLI returned invalid JSON") from exc
    if objects is None:
        objects = []
    if not isinstance(objects, list):
        raise RuntimeError("AWS CLI returned an unexpected object-list response")
    if any(not isinstance(item, dict) or not isinstance(item.get("Key"), str) for item in objects):
        raise RuntimeError("AWS CLI returned an object without a valid Key")
    for item in objects:
        if "Size" in item and (type(item["Size"]) is not int or item["Size"] < 0):
            raise RuntimeError("AWS CLI returned an invalid object Size")
    return objects


def parse_s3_journal_key(key: str, expected_index: str) -> dict[str, object] | None:
    parts = key.split("/")
    if len(parts) != 4 or any(part in {"", ".", ".."} for part in parts):
        return None
    if parts[0] != expected_index:
        return None
    if parts[2] != "rawdata" or parts[3] not in JOURNALS:
        return None
    bucket = parse_bucket_name(parts[1])
    if bucket is None:
        return None
    return {"key": key, "bucket": bucket}


def filter_s3_bucket_objects(
    objects: Iterable[dict[str, object]],
    index: str,
    oldest_epoch_time: int,
    newest_epoch_time: int,
) -> list[dict[str, object]]:
    matched: dict[str, dict[str, object]] = {}
    for item in objects:
        key = item.get("Key")
        if not isinstance(key, str):
            continue
        parsed = parse_s3_journal_key(key, index)
        if parsed is None:
            continue
        bucket = parsed["bucket"]
        assert isinstance(bucket, dict)
        if (
            int(bucket["newest"]) >= oldest_epoch_time
            and int(bucket["oldest"]) <= newest_epoch_time
        ):
            matched.setdefault(str(bucket["name"]), parsed)
    return sorted(
        matched.values(),
        key=lambda item: (
            int(item["bucket"]["oldest"]),  # type: ignore[index]
            int(item["bucket"]["newest"]),  # type: ignore[index]
            str(item["bucket"]["name"]),  # type: ignore[index]
        ),
    )


def safe_s3_target(root: str | os.PathLike[str], key: str) -> Path:
    parts = key.split("/")
    if not parts or any(
        part in {"", ".", ".."} or "\\" in part or ":" in part
        or any(ord(char) < 32 for char in part) for part in parts
    ):
        raise RuntimeError(f"Unsafe S3 key: {key}")
    root_path = Path(root).expanduser().resolve()
    current = root_path
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeError(f"Symlink in S3 destination: {current}")
    target = root_path.joinpath(*parts).resolve()
    if target != root_path and root_path not in target.parents:
        raise RuntimeError(f"S3 key escapes the destination directory: {key}")
    return target


def download_s3_objects(
    objects: Sequence[dict[str, object]],
    bucket_name: str,
    destination_root: str | os.PathLike[str],
    endpoint: str = "",
    aws_binary: str = "aws",
    runner: Runner = run_command,
) -> list[Path]:
    downloaded: list[Path] = []
    for item in objects:
        key = str(item["key"])
        target = safe_s3_target(destination_root, key)
        if target.exists():
            raise RuntimeError(f"Target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f"{target.name}.part-{uuid.uuid4().hex}")
        command = [
            aws_binary,
            "s3api",
            "get-object",
            "--bucket",
            bucket_name,
            "--key",
            key,
            str(temporary),
        ]
        if endpoint:
            command.extend(["--endpoint-url", endpoint])
        if item.get("etag"):
            command.extend(["--if-match", str(item["etag"])])
        try:
            runner(command, check=True, capture_output=True, text=True)
            if "size" in item and temporary.stat().st_size != item["size"]:
                raise RuntimeError(f"Size mismatch for S3 object {key!r}")
            os.replace(temporary, target)
        except (subprocess.SubprocessError, OSError) as exc:
            raise RuntimeError(
                f"Unable to download S3 object {key!r}: {_failure_text(exc)}"
            ) from exc
        finally:
            temporary.unlink(missing_ok=True)
        print(f"Downloaded {key} to {target}")
        downloaded.append(target)
    return downloaded


def restore_buckets_from_s3(
    index: str,
    frozendb: str,
    oldest_epoch_time: int,
    newest_epoch_time: int,
    bucket_name: str,
    s3_endpoint: str = "",
    aws_binary: str = "aws",
    runner: Runner = run_command,
    download: bool = True,
) -> list[str]:
    objects = list_s3_objects(
        bucket_name, index, s3_endpoint, aws_binary, runner
    )
    matched = filter_s3_bucket_objects(
        objects, index, oldest_epoch_time, newest_epoch_time
    )
    print(f"The number of bucket(s) found in S3: {len(matched)}.")
    names = [str(item["bucket"]["name"]) for item in matched]  # type: ignore[index]
    if download and matched:
        root = Path(frozendb).expanduser().resolve()
        selected = set(names)
        manifest: list[dict[str, object]] = []
        for item in objects:
            key = str(item["Key"])
            parts = key.split("/")
            if len(parts) < 3 or parts[0] != index or parts[1] not in selected:
                continue
            # S3 directory markers contain no archive data.
            if key.endswith("/") and item.get("Size") == 0:
                continue
            safe_s3_target(root, key)
            record: dict[str, object] = {"key": key}
            if "Size" in item:
                record["size"] = item["Size"]
            if item.get("ETag"):
                record["etag"] = item["ETag"]
            manifest.append(record)
        destination = safe_s3_target(root, index)
        for name in names:
            target = destination / name
            if os.path.lexists(target):
                raise RuntimeError(f"S3 cache bucket already exists: {target}")
        root.mkdir(parents=True, exist_ok=True)
        download_size = sum(int(item.get("size", 0)) for item in manifest)
        if download_size > shutil.disk_usage(root).free:
            raise RuntimeError(f"Insufficient disk space to download {download_size} bytes")
        # Publish only after *all* files have downloaded successfully; never mix
        # a fresh archive with files left by a previous restore attempt.
        with tempfile.TemporaryDirectory(prefix=".s3-staging-", dir=root) as staging:
            download_s3_objects(
                manifest, bucket_name, staging, s3_endpoint, aws_binary, runner
            )
            staged_source = Path(staging) / index
            for name in names:
                validate_bucket_tree(staged_source / name)
            destination.mkdir(parents=True, exist_ok=True)
            _commit_staged_buckets(staged_source, destination, names)
    return names


def _existing_bucket_ids(index_root: Path, destination: Path) -> dict[str, Path]:
    existing: dict[str, Path] = {}
    for directory in {destination, *(index_root / name for name in ("db", "colddb", "thaweddb"))}:
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            if not entry.is_dir():
                continue
            bucket = parse_bucket_name(entry.name)
            if bucket:
                existing.setdefault(str(bucket["id"]), entry)
    return existing


def validate_bucket_tree(bucket: Path) -> int:
    """Reject unsafe archive entries and return the total regular-file size."""
    if not bucket.is_dir() or bucket.is_symlink():
        raise RuntimeError(f"Source bucket is not a safe directory: {bucket}")
    total = 0
    pending = [bucket]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    raise RuntimeError(f"Symlink in archive bucket: {entry.path}")
                if stat.S_ISDIR(info.st_mode):
                    pending.append(Path(entry.path))
                elif stat.S_ISREG(info.st_mode):
                    total += info.st_size
                else:
                    raise RuntimeError(f"Non-regular archive file: {entry.path}")
    if not any(
        (bucket / "rawdata" / name).is_file()
        and (bucket / "rawdata" / name).stat().st_size > 0
        for name in JOURNALS
    ):
        raise RuntimeError(f"Missing or empty rawdata journal in {bucket}")
    return total


def _commit_staged_buckets(staging: Path, destination: Path, names: Sequence[str]) -> list[Path]:
    committed: list[Path] = []
    try:
        for name in names:
            target = destination / name
            if os.path.lexists(target):
                raise RuntimeError(f"Target appeared during copy: {target}")
            (staging / name).rename(target)
            committed.append(target)
    except BaseException:
        for target in reversed(committed):
            shutil.rmtree(target)
        raise
    return committed


@contextmanager
def destination_lock(destination: str | os.PathLike[str]):
    """Serialize this CLI's restore jobs through rebuild/restart.

    A hard kill leaves a lock intentionally: operators must inspect the target
    before removing it. Splunk and other tools do not participate in this lock.
    """
    root = Path(destination).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".restore.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise RuntimeError(f"Restore lock already exists; inspect before retrying: {lock}") from exc
    try:
        with handle:
            handle.write(f"pid={os.getpid()}\n")
        yield
    finally:
        lock.unlink()


def copy_buckets(
    source_path: str | os.PathLike[str],
    dest_path: str | os.PathLike[str],
    buckets_found: Sequence[str],
) -> list[Path]:
    """Preflight and stage copies; each rename is atomic, not the entire batch."""

    if not buckets_found:
        raise RuntimeError("No buckets were selected for copying")
    source = Path(source_path).expanduser().resolve()
    destination = Path(dest_path).expanduser().resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise RuntimeError("Source and destination paths overlap")
    destination.mkdir(parents=True, exist_ok=True)
    existing_ids = _existing_bucket_ids(destination.parent, destination)
    incoming_ids: set[str] = set()
    total_size = 0

    for name in buckets_found:
        bucket = parse_bucket_name(name)
        if bucket is None:
            raise RuntimeError(f"Invalid bucket name selected for copying: {name}")
        source_bucket = source / name
        target_bucket = destination / name
        total_size += validate_bucket_tree(source_bucket)
        if os.path.lexists(target_bucket):
            raise RuntimeError(f"Target bucket already exists: {target_bucket}")
        bucket_id = str(bucket["id"])
        if bucket_id in incoming_ids:
            raise RuntimeError(f"Duplicate incoming bucket ID: {bucket_id}")
        if bucket_id in existing_ids:
            raise RuntimeError(
                f"Bucket ID {bucket_id!r} conflicts with {existing_ids[bucket_id]}"
            )
        incoming_ids.add(bucket_id)

    if total_size > shutil.disk_usage(destination).free:
        raise RuntimeError(f"Insufficient disk space to copy {total_size} bytes to {destination}")

    staging = destination / f".restore-staging-{uuid.uuid4().hex}"
    try:
        staging.mkdir()
        for name in buckets_found:
            # Preserve any link introduced after preflight instead of following
            # it outside the archive; the staged validation then rejects it.
            shutil.copytree(source / name, staging / name, symlinks=True)
            validate_bucket_tree(staging / name)
        committed = _commit_staged_buckets(staging, destination, buckets_found)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    print(f"Successfully copied {len(committed)} bucket(s).")
    return committed


def splunk_binary(splunk_home: str | os.PathLike[str]) -> Path:
    binary = Path(splunk_home).expanduser().resolve() / "bin" / "splunk"
    if not binary.is_file():
        raise RuntimeError(f"Splunk executable does not exist: {binary}")
    if not os.access(binary, os.X_OK):
        raise RuntimeError(f"Splunk file is not executable: {binary}")
    return binary


def check_data_integrity(
    source_path: str | os.PathLike[str],
    buckets_found: Sequence[str],
    splunk_home: str | os.PathLike[str],
    allow_unverified: bool = False,
    runner: Runner = run_command,
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Return allowed, failed, passed, and unverified bucket names."""

    source = Path(source_path).expanduser().resolve()
    binary = splunk_binary(splunk_home)
    failed: list[str] = []
    passed: list[str] = []
    unverified: list[str] = []

    for name in buckets_found:
        if parse_bucket_name(name) is None:
            raise RuntimeError(f"Invalid bucket name: {name}")
        validate_bucket_tree(source / name)
        rawdata = source / name / "rawdata"
        if not rawdata.is_dir():
            eprint(f"Integrity check failed: rawdata directory is missing for {name}")
            failed.append(name)
            continue
        has_hash = any(
            entry.is_file() and entry.name.startswith("l2Hash")
            for entry in rawdata.iterdir()
        )
        if not has_hash:
            unverified.append(name)
            continue
        command = [
            str(binary),
            "check-integrity",
            "-bucketPath",
            str(source / name),
        ]
        try:
            result = runner(command, check=True, capture_output=True, text=True)
        except (subprocess.SubprocessError, OSError) as exc:
            eprint(f"Integrity command failed for {name}: {_failure_text(exc)}")
            failed.append(name)
            continue
        matches = INTEGRITY_PATTERN.findall(_command_output(result))
        if not matches:
            eprint(f"Could not parse integrity output for {name}")
            failed.append(name)
        elif any(int(failed_count) > 0 for _, failed_count in matches) or not any(
            int(succeeded) > 0 for succeeded, _ in matches
        ):
            failed.append(name)
        else:
            passed.append(name)

    allowed_names = set(passed)
    if allow_unverified:
        allowed_names.update(unverified)
    allowed = [name for name in buckets_found if name in allowed_names]
    print(
        "Data integrity check completed. "
        f"Failed: {len(failed)}, Passed: {len(passed)}, "
        f"Unverified: {len(unverified)}"
    )
    return allowed, failed, passed, unverified


def log_data_integrity(
    buckets_not_checked_integrity: Sequence[str],
    buckets_failed_integrity: Sequence[str],
    buckets_passed_integrity: Sequence[str],
    splunk_home: str | os.PathLike[str],
) -> Path:
    log_directory = Path(splunk_home).expanduser().resolve() / "var" / "log" / "splunk"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / datetime.now().strftime(
        "%Y-%m-%d-%H-%M-%S-%f_integrity_check.log"
    )
    with log_path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(f"Timestamp: {datetime.now().strftime(DATE_FORMAT)}\n\n")
        for title, values in (
            ("Buckets Failed", buckets_failed_integrity),
            ("Buckets Passed", buckets_passed_integrity),
            ("Buckets Unverified", buckets_not_checked_integrity),
        ):
            handle.write(f"---- {title} ----\n")
            for name in values:
                handle.write(f"- {name}\n")
            handle.write("\n")
    return log_path


def rebuild_buckets(
    buckets_found: Sequence[str],
    dest_path: str | os.PathLike[str],
    dest_index: str,
    splunk_home: str | os.PathLike[str],
    runner: Runner = run_command,
) -> tuple[list[str], list[str]]:
    binary = splunk_binary(splunk_home)
    destination = Path(dest_path).expanduser().resolve()
    passed: list[str] = []
    failed: list[str] = []
    for name in buckets_found:
        command = [str(binary), "rebuild", str(destination / name), dest_index]
        try:
            result = runner(command, check=True, capture_output=True, text=True)
        except (subprocess.SubprocessError, OSError) as exc:
            eprint(f"Error rebuilding bucket {name!r}: {_failure_text(exc)}")
            failed.append(name)
            continue
        output = _command_output(result)
        if output:
            print(output)
        passed.append(name)
    print(
        f"Buckets rebuild completed. Success: {len(passed)}, Failed: {len(failed)}"
    )
    return passed, failed


def restart_splunk(
    splunk_home: str | os.PathLike[str],
    runner: Runner = run_command,
) -> None:
    binary = splunk_binary(splunk_home)
    try:
        result = runner(
            [str(binary), "restart"], check=True, capture_output=True, text=True
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"Unable to restart Splunk: {_failure_text(exc)}") from exc
    output = _command_output(result)
    if output:
        print(output)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Restore archived Splunk buckets (procedural v1.1).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-f", "--frozendb", help="Frozen bucket root path")
    parser.add_argument("-t", "--thaweddb", help="Target thaweddb path")
    parser.add_argument("-i", "--index", help="Target index name")
    escaped_format = DATE_FORMAT.replace("%", "%%")
    parser.add_argument("-o", "--oldest_time", help=f"Oldest time ({escaped_format})")
    parser.add_argument("-n", "--newest_time", help=f"Newest time ({escaped_format})")
    parser.add_argument("-s", "--splunk_home", help="Splunk home path")
    parser.add_argument("--restart_splunk", action="store_true")
    parser.add_argument("--check_integrity", action="store_true")
    parser.add_argument(
        "--allow_unverified_buckets",
        action="store_true",
        help="Allow unsigned buckets when integrity checking is requested",
    )
    parser.add_argument("-s3", "--s3_path", help="Custom S3 endpoint URL")
    parser.add_argument("-s3b", "--s3_default_bucket", help="S3 bucket name")
    parser.add_argument("--timezone", help="IANA timezone, for example Europe/Istanbul")
    parser.add_argument("--aws_binary", default="aws", help="AWS CLI executable")
    parser.add_argument("--command_timeout", type=float, default=3600,
                        help="Maximum seconds per AWS/Splunk command")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def archive_help(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def validate_args(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> bool:
    if args.index:
        try:
            validate_index(args.index)
        except ValueError as exc:
            parser.error(str(exc))
    if not math.isfinite(args.command_timeout) or args.command_timeout <= 0:
        parser.error("--command_timeout must be a finite positive number")
    if bool(args.oldest_time) != bool(args.newest_time):
        parser.error("--oldest_time and --newest_time must be supplied together")
    if args.s3_path and not args.s3_default_bucket:
        parser.error("--s3_path requires --s3_default_bucket")
    if args.allow_unverified_buckets and not args.check_integrity:
        parser.error("--allow_unverified_buckets requires --check_integrity")

    restore_mode = bool(args.oldest_time and args.newest_time)
    if restore_mode:
        required = {
            "--frozendb": args.frozendb,
            "--thaweddb": args.thaweddb,
            "--index": args.index,
            "--splunk_home": args.splunk_home,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            parser.error(f"Restore mode requires: {', '.join(missing)}")
    elif args.s3_default_bucket:
        if not args.index:
            parser.error("S3 inventory mode requires --index")
    elif not args.frozendb:
        parser.error("Local inventory mode requires --frozendb")
    return restore_mode


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    restore_mode = validate_args(parser, args)
    runner = partial(run_command, timeout=args.command_timeout)

    try:
        if restore_mode:
            oldest, newest = handle_dates(
                args.oldest_time, args.newest_time, args.timezone
            )
            frozen_root = Path(args.frozendb).expanduser().resolve()
            source_path = frozen_root / args.index
            splunk_binary(args.splunk_home)
            destination = Path(args.thaweddb).expanduser().resolve()
            resolved_source = source_path.resolve()
            if (resolved_source == destination or resolved_source in destination.parents
                    or destination in resolved_source.parents):
                raise RuntimeError("Source and destination paths overlap")

            if args.s3_default_bucket:
                buckets = restore_buckets_from_s3(
                    args.index,
                    str(frozen_root),
                    oldest,
                    newest,
                    args.s3_default_bucket,
                    args.s3_path or "",
                    args.aws_binary,
                    runner=runner,
                )
            else:
                buckets = find_buckets(source_path, oldest, newest)
            if not buckets:
                raise RuntimeError("No matching buckets were found")

            if args.check_integrity:
                allowed, failed, passed, unverified = check_data_integrity(
                    source_path,
                    buckets,
                    args.splunk_home,
                    args.allow_unverified_buckets,
                    runner=runner,
                )
                log_path = log_data_integrity(
                    unverified, failed, passed, args.splunk_home
                )
                print(f"Integrity log: {log_path}")
                if failed or (unverified and not args.allow_unverified_buckets):
                    raise RuntimeError(
                        "Integrity verification rejected selected buckets; "
                        "nothing will be copied or rebuilt"
                    )
                buckets = allowed
                if not buckets:
                    raise RuntimeError("No buckets remain after integrity verification")

            with destination_lock(args.thaweddb):
                copy_buckets(source_path, args.thaweddb, buckets)
                _, failed = rebuild_buckets(
                    buckets, args.thaweddb, args.index, args.splunk_home, runner=runner
                )
                if failed:
                    raise RuntimeError(
                        f"{len(failed)} bucket(s) failed to rebuild; "
                        "copies remain in the target for diagnosis; "
                        "Splunk will not be restarted"
                    )
                if args.restart_splunk:
                    restart_splunk(args.splunk_home, runner=runner)
            return 0

        newest = int(time.time())
        if args.s3_default_bucket:
            buckets = restore_buckets_from_s3(
                args.index,
                args.frozendb or ".",
                0,
                newest,
                args.s3_default_bucket,
                args.s3_path or "",
                args.aws_binary,
                runner=runner,
                download=False,
            )
            index_name = args.index
        else:
            source_path = Path(args.frozendb).expanduser()
            if args.index:
                source_path = source_path / args.index
            buckets = find_buckets(source_path, 0, newest)
            index_name = args.index or source_path.resolve().name
        find_oldest_and_newest_bucket_dates(
            buckets, index=index_name, timezone_name=args.timezone
        )
        return 0
    except (RuntimeError, ValueError, OSError, OverflowError) as exc:
        eprint(f"Error: {exc}")
        return 1
    except KeyboardInterrupt:
        eprint("Interrupted; inspect the target before retrying (rebuild may be incomplete)")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
