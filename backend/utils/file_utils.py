from pathlib import Path

from backend.core.config import UPLOAD_DIR


def unique_csv_dest(upload_dir: Path, filename: str) -> tuple[Path, str]:
    """重命名逻辑：已有同名则改为 stem_1.csv、stem_2.csv … 直至不冲突。"""
    candidate = upload_dir / filename
    if not candidate.exists():
        return candidate, filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    n = 1
    while True:
        alt_name = f"{stem}_{n}{suffix}"
        candidate = upload_dir / alt_name
        if not candidate.exists():
            return candidate, alt_name
        n += 1


def safe_upload_file_path(filename: str) -> Path | None:
    """安全检查：禁止路径分隔符，解析后确保不越出 UPLOAD_DIR。"""
    if not filename or "/" in filename or "\\" in filename:
        return None
    target = (UPLOAD_DIR / filename).resolve()
    root = UPLOAD_DIR.resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target
