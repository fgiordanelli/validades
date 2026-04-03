from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

PRINT_JOBS_TABLE = os.getenv("PRINT_JOBS_TABLE", "print_jobs")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "2"))
PRINTER_QUEUE = os.getenv("PRINTER_QUEUE", "LABEL")


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def fetch_pending_jobs(client: Client) -> list[dict[str, Any]]:
    result = (
        client.table(PRINT_JOBS_TABLE)
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(20)
        .execute()
    )
    return result.data or []


def update_job_status(client: Client, job_id: int, status: str, error_message: str | None = None) -> None:
    payload: dict[str, Any] = {"status": status}
    if status == "printed":
        payload["printed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        payload["printer_name"] = PRINTER_QUEUE
        payload["error_message"] = None
    elif error_message is not None:
        payload["error_message"] = error_message[:500]

    client.table(PRINT_JOBS_TABLE).update(payload).eq("id", job_id).execute()


def print_raw_windows(raw_text: str) -> None:
    try:
        import win32print  # type: ignore
    except ImportError as exc:
        raise RuntimeError("No Windows, instale pywin32: pip install pywin32") from exc

    printer_name = PRINTER_QUEUE
    handle = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(handle, 1, ("Etiqueta", None, "RAW"))
        win32print.StartPagePrinter(handle)
        win32print.WritePrinter(handle, raw_text.encode("utf-8"))
        win32print.EndPagePrinter(handle)
        win32print.EndDocPrinter(handle)
    finally:
        win32print.ClosePrinter(handle)


def print_raw_unix(raw_text: str) -> None:
    result = subprocess.run(
        ["lp", "-d", PRINTER_QUEUE, "-o", "raw"],
        input=raw_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "Falha ao imprimir.").strip()
        raise RuntimeError(error)


def print_job(raw_text: str) -> None:
    if sys.platform.startswith("win"):
        print_raw_windows(raw_text)
    else:
        print_raw_unix(raw_text)


def main() -> None:
    client = get_client()
    print(f"Escutando fila '{PRINT_JOBS_TABLE}' a cada {POLL_SECONDS}s. Impressora: {PRINTER_QUEUE}")
    while True:
        try:
            jobs = fetch_pending_jobs(client)
            for job in jobs:
                job_id = job["id"]
                tspl = job["tspl"]
                try:
                    update_job_status(client, job_id, "printing")
                    print_job(tspl)
                    update_job_status(client, job_id, "printed")
                    print(f"Job {job_id} impresso com sucesso.")
                except Exception as exc:
                    update_job_status(client, job_id, "error", str(exc))
                    print(f"Erro no job {job_id}: {exc}")
        except Exception as exc:
            print(f"Erro ao consultar a fila: {exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
