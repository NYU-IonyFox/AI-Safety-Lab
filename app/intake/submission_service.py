from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from app.schemas import SubmissionTarget


@dataclass
class SubmissionResolution:
    source_type: str
    target_name: str
    resolved_path: str
    description: str
    github_url: str = ""
    local_path: str = ""
    cleanup_path: str = ""


class SubmissionError(RuntimeError):
    pass


def resolve_submission(submission: SubmissionTarget | None) -> SubmissionResolution | None:
    if submission is None:
        return None

    source_type = submission.source_type
    target_name = submission.target_name.strip()
    description = submission.description.strip()

    if source_type == "local_path":
        path = Path(submission.local_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise SubmissionError(f"Local path does not exist or is not a directory: {path}")
        return SubmissionResolution(
            source_type=source_type,
            target_name=target_name or path.name,
            resolved_path=str(path),
            description=description,
            local_path=str(path),
        )

    if source_type == "github_url":
        github_url = submission.github_url.strip()
        parsed = urlparse(github_url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
            raise SubmissionError("Only https://github.com/... URLs are supported for GitHub intake.")
        tmpdir = tempfile.mkdtemp(prefix="ai-safety-lab-repo-")
        clone_cwd = str(Path(tmpdir).parent)
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", github_url, tmpdir],
                check=True,
                capture_output=True,
                text=True,
                cwd=clone_cwd,
            )
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise SubmissionError(exc.stderr.strip() or f"git clone failed for {github_url}") from exc
        except OSError as exc:
            shutil.rmtree(tmpdir, ignore_errors=True)
            raise SubmissionError(f"git clone failed for {github_url}: {exc}") from exc
        repo_name = Path(parsed.path.rstrip("/")).name.removesuffix(".git") or "github-repo"
        return SubmissionResolution(
            source_type=source_type,
            target_name=target_name or repo_name,
            resolved_path=tmpdir,
            description=description,
            github_url=github_url,
            cleanup_path=tmpdir,
        )

    return SubmissionResolution(
        source_type=source_type,
        target_name=target_name or "submitted-project",
        resolved_path="",
        description=description,
    )


def cleanup_submission(resolution: SubmissionResolution | None) -> None:
    if resolution is None or not resolution.cleanup_path:
        return
    shutil.rmtree(resolution.cleanup_path, ignore_errors=True)


def fetch_github_content(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "github.com":
        raise SubmissionError("Only https://github.com/... URLs are supported.")

    tmpdir = tempfile.mkdtemp(prefix="safe-github-")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", url, tmpdir],
            check=True,
            capture_output=True,
            text=True,
        )

        from app.analyzers import summarize_repository

        repo_name = Path(parsed.path.rstrip("/")).name.removesuffix(".git") or "github-repo"
        summary = summarize_repository(tmpdir, target_name=repo_name, source_type="github_url")

        root = Path(tmpdir)
        key_files: dict[str, str] = {}
        for rel_name in summary.notable_files:
            file_path = root / rel_name
            if file_path.is_file():
                try:
                    key_files[rel_name] = file_path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    pass

        structural_tags: list[str] = []
        if summary.framework and summary.framework != "Unknown":
            structural_tags.append(f"framework:{summary.framework}")
        for route in summary.entrypoints[:5]:
            structural_tags.append(f"route:{route}")
        for dep in summary.dependencies[:5]:
            structural_tags.append(f"dep:{dep}")

        return {
            "url": url,
            "key_files": key_files,
            "analyzer_summary": summary.summary,
            "structural_tags": structural_tags,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
