from pathlib import Path


def running_in(stat: Path, pgid: int) -> bool:
    try:
        fields = stat.read_text().rsplit(")", 1)[1].split()
    except OSError:
        return False
    return fields[2] == str(pgid) and fields[0] not in ("Z", "X")
