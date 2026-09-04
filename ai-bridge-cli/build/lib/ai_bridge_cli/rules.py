from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Message:
    path: Path
    from_: str | None = None
    to: str | None = None
    date: str | None = None
    type: str | None = None
    thread: str | None = None
    body: str = ""


VALID_TYPES = {"greeting", "question", "proposal", "result", "status", "comment", "other"}


def load_message(path: Path) -> Message:
    import yaml

    text = path.read_text(encoding="utf-8")
    fm, body = "", text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            fm = text[3:end].strip()
            body = text[end + 3 :].strip()
    data = {}
    if fm:
        try:
            data = yaml.safe_load(fm) or {}
        except Exception:
            data = {}
    return Message(
        path=path,
        from_=data.get("from"),
        to=data.get("to"),
        date=data.get("date"),
        type=data.get("type"),
        thread=data.get("thread"),
        body=body,
    )
