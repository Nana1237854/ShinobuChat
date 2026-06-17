from datetime import datetime


def local_now() -> datetime:
    return datetime.now().astimezone()
