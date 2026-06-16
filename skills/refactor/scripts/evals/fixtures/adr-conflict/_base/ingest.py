from store import save


def ingest(record: dict) -> None:
    validated = {**record, "ok": True}
    save(validated)
