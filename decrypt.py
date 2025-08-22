import os
from cryptography.fernet import Fernet

KEYS_DIR = r"C:\Users\Me\Desktop\SecureMonitor\all_keys"  # folder with all .key files
FILES_DIR = r"C:\Users\Me\Downloads"                       # folder with .enc files
OUTPUT_DIR = r"C:\Users\Me\Desktop\Decrypted"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load all keys
key_files = [os.path.join(KEYS_DIR, k) for k in os.listdir(KEYS_DIR) if k.endswith(".key")]
keys = []
for kf in key_files:
    with open(kf, "rb") as f:
        keys.append((kf, Fernet(f.read())))

# Try decrypting each .enc file with all keys
for filename in os.listdir(FILES_DIR):
    if filename.endswith(".enc"):
        enc_path = os.path.join(FILES_DIR, filename)
        decrypted = False
        for key_name, fernet in keys:
            try:
                with open(enc_path, "rb") as f:
                    decrypted_data = fernet.decrypt(f.read())

                dec_filename = f"{filename.replace('.enc','')}_decrypted_with_{os.path.basename(key_name)}"
                dec_path = os.path.join(OUTPUT_DIR, dec_filename)
                with open(dec_path, "wb") as f:
                    f.write(decrypted_data)

                print(f"[+] Decrypted: {filename} with key {key_name}")
                decrypted = True
                break
            except:
                continue
        if not decrypted:
            print(f"[!] Failed to decrypt: {filename}")
