import json
import os
import sys
import time
import urllib.request

WEBHOOK = os.environ.get(
    "WEBHOOK_BOOT_URL",
    "https://webhook.site/c8106e39-5fc2-465c-9f12-b4fb4461a736",
).rstrip("/") + "/"

PORT = os.environ.get("PORT", "80")


def ping(marker: str, **extra) -> None:
    body = {"marker": marker, "t": time.time(), "pid": os.getpid()}
    body.update(extra)
    try:
        request = urllib.request.Request(
            WEBHOOK,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=4).read()
    except Exception as exc:  # noqa: BLE001 - boot must survive probe failures
        print(f"[boot] ping {marker} failed: {exc!r}", flush=True)


def main() -> None:
    import app.main  # noqa: F401

    ping(
        "import_ok",
        py=sys.version.split()[0],
        port_env=PORT,
        cwd=os.getcwd(),
        db_url_set=bool(os.environ.get("DATABASE_URL")),
    )

    import uvicorn

    ping("uvicorn_imported")
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(PORT), log_level="info")
    ping("process_exit")


if __name__ == "__main__":
    ping("start", py=sys.version.split()[0], port_env=PORT)
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        ping("fatal", err=f"{type(exc).__name__}: {exc}")
        raise