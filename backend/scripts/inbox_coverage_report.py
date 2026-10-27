"""Read-only Inbox coverage report. Counts only: no senders, subjects or email text.

Compares what Gmail lists for recent windows with what ACE has stored, and shows
how stored email was decided and under which parser version. Run it inside the
API container so it uses the real settings (PostgreSQL only):

    docker compose --env-file .env -f deploy/oracle/compose.yaml exec -T api \\
        python -m backend.scripts.inbox_coverage_report

Every database connection is read-only. Gmail is only listed (message IDs), never
read, so nothing is imported, decided or changed.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.inbox import gmail
from backend.app.inbox.reconcile import PARSER_VERSION

WINDOWS = (7, 30, 90, 365, None)
# Senders that are recruiting systems, where an unrecognised email may still be about an application.
PLATFORMS = ("workday", "greenhouse", "lever.co", "ashbyhq", "smartrecruiters", "icims", "jobvite", "taleo", "successfactors", "eightfold", "oraclecloud")
APPLICATION_WORDS = ("applica", "interest", "candida", "interview", "position")


def gmail_ids(token: str, days: int | None) -> tuple[list[str], bool]:
    """Follow every ID page. None means all retained mail, including Spam/Trash."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days + 1)).strftime("%Y/%m/%d") if days is not None else None
    ids: dict[str, None] = {}
    page: str | None = None
    seen: set[str] = set()
    while True:
        params = {"maxResults": 500}
        if cutoff:
            params["q"] = f"after:{cutoff}"
        else:
            params["includeSpamTrash"] = "true"
        if page:
            params["pageToken"] = page
        batch = gmail.get_json("/messages", token, params)
        ids.update((str(item["id"]), None) for item in batch.get("messages", []) if item.get("id"))
        page = batch.get("nextPageToken")
        if not page:
            return list(ids), True
        if page in seen:
            return list(ids), False
        seen.add(page)


def main() -> int:
    print(f"observed_at: {datetime.now(timezone.utc).isoformat()}", flush=True)
    settings = get_settings()
    engine = create_engine(settings.database_url, connect_args={"options": "-c default_transaction_read_only=on"})
    with Session(engine) as db:
        conn = db.execute(text("select state, history_id is not null, preview_complete, last_synced_at, last_error is not null, encrypted_refresh_token from gmail_connections order by id limit 1")).first()
        if conn is None:
            print("No Gmail connection.")
            return 1
        print(f"parser in this build: {PARSER_VERSION}")
        print(f"connection: state={conn[0]} has_cursor={conn[1]} preview_complete={conn[2]} last_sync={conn[3]} has_error={conn[4]}")
        total, oldest, newest = db.execute(text("select count(*), min(received_at), max(received_at) from gmail_messages")).one()
        print(f"stored: {total} emails from {oldest} to {newest}")
        for label, column in (("decision", "decision"), ("parser version", "parser_version"), ("classification", "classification")):
            rows = db.execute(text(f"select {column}, count(*) from gmail_messages group by 1 order by 2 desc")).all()
            print(f"by {label}: " + ", ".join(f"{key}={count}" for key, count in rows))
        stale = db.execute(text("select count(*) from gmail_messages where parser_version <> :v"), {"v": PARSER_VERSION}).scalar()
        print(f"stored under an older parser: {stale}")
        sender_clause = " or ".join(f"sender ilike :s{i}" for i in range(len(PLATFORMS)))
        text_clause = " or ".join(f"subject ilike :t{i} or snippet ilike :t{i}" for i in range(len(APPLICATION_WORDS)))
        params = {f"s{i}": f"%{word}%" for i, word in enumerate(PLATFORMS)} | {f"t{i}": f"%{word}%" for i, word in enumerate(APPLICATION_WORDS)}
        for label, clause in (("from recruiting systems", sender_clause), ("with application words", text_clause)):
            count = db.execute(text(f"select count(*) from gmail_messages where decision = 'ignored' and ({clause})"), params).scalar()
            print(f"ignored ('No outcome found') {label}: {count}")
        linked = db.execute(text("select count(*) from gmail_messages where decision = 'receipt' and selected_application_key is not null")).scalar()
        receipts = db.execute(text("select count(*) from gmail_messages where decision = 'receipt'")).scalar()
        print(f"acknowledgements linked to an application: {linked} of {receipts}")
        applied = db.execute(text("select count(*), min(applied_at) from job_marks where applied_at is not null")).one()
        external = db.execute(text("select count(*) from external_applications")).scalar()
        print(f"applications: {applied[0]} applied marks (oldest {applied[1]}) + {external} external")
        stored_ids = set(db.scalars(text("select gmail_id from gmail_messages")))
        refresh = bytes(conn[5])
        db.rollback()
    token = gmail.access_token(gmail.decrypt_token(refresh, settings.gmail_token_key), client_id=settings.gmail_client_id, client_secret=settings.gmail_client_secret)
    complete_all = True
    print("Windowed queries include one cutoff-buffer day and default Spam/Trash exclusions.")
    print("All time has no date cutoff and includes retained Spam and Trash. Permanently deleted mail is unavailable.")
    for days in WINDOWS:
        ids, complete = gmail_ids(token, days)
        present = sum(1 for item in ids if item in stored_ids)
        label = "all time, including Spam/Trash" if days is None else f"last {days} days"
        print(f"gmail, {label}: {len(ids)} listed (complete={complete}); in ACE: {present}; missing: {len(ids) - present}")
        if days is None:
            print(f"stored evidence no longer in the retained mailbox listing: {len(stored_ids - set(ids))}")
        complete_all = complete_all and complete
    return 0 if complete_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
