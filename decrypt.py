
import os
import argparse
from pathlib import Path
import pyzipper

def extract_zip(zip_path: Path, output_dir: Path, password: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    with pyzipper.AESZipFile(zip_path, "r") as zf:
        zf.setpassword(password.encode("utf-8"))
        zf.extractall(path=output_dir)

def main():
    parser = argparse.ArgumentParser(description="Extract AES-Encrypted ZIPs (pyzipper).")
    parser.add_argument("--input", "-i", default=".", help="Folder containing ZIP files.")
    parser.add_argument("--output", "-o", default="./extracted", help="Where to extract files.")
    parser.add_argument("--password", "-p", default=None, help="ZIP password (else env ZIP_PASSWORD).")
    args = parser.parse_args()

    password = args.password or os.environ.get("ZIP_PASSWORD")
    if not password:
        raise SystemExit("Error: Provide --password or set ZIP_PASSWORD in environment.")

    in_dir = Path(args.input).expanduser().resolve()
    out_dir = Path(args.output).expanduser().resolve()

    zips = [p for p in in_dir.iterdir() if p.is_file() and p.suffix.lower() == ".zip"]
    if not zips:
        print("No .zip files found in input folder:", in_dir)
        return

    for z in zips:
        try:
            print(f"Extracting {z.name} -> {out_dir}")
            extract_zip(z, out_dir, password)
            print(f"Done: {z.name}")
        except RuntimeError as e:
            # Bad password or corrupted archive
            print(f"Failed: {z.name}: {e}")
        except Exception as e:
            print(f"Error extracting {z.name}: {e}")

if __name__ == "__main__":
    main()
