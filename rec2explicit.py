#!/usr/bin/env python3
"""
rec2expLE.py – Make every DICOM in a directory tree Explicit VR Little Endian.

Strategy:
  • try dcmdjpeg +te  (decompress JPEG/RLE → Explicit LE)
  • if that fails (exit‑code ≠ 0), try dcmconv +te (implicit → explicit)
  • overwrite the original atomically
"""
import os, subprocess, argparse, tempfile
from tqdm import tqdm
from shutil import which
from concurrent.futures import ThreadPoolExecutor, as_completed

def tool_ok(name: str) -> bool:
    return which(name) is not None

def to_explicit_le(path: str):
    """Convert *path* to Explicit VR Little Endian in‑place.
       Returns (path, ok: bool, method: str)."""
    dirname = os.path.dirname(path)
    tmp_fd, tmp = tempfile.mkstemp(suffix=".dcm", dir=dirname); os.close(tmp_fd)

    # first choice: dcmdjpeg (+te is default output anyway)
    result = subprocess.run(
        ["dcmdjpeg", "+te", path, tmp],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    method = "dcmdjpeg"
    if result.returncode != 0:
        # fall back to dcmconv for non‑JPEG files
        result = subprocess.run(
            ["dcmconv", "+te", path, tmp],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        method = "dcmconv"

    if result.returncode == 0:
        os.replace(tmp, path)          # atomic on POSIX
        return path, True, method

    # both tools failed → clean up
    os.remove(tmp)
    return path, False, method

def walk_convert(root: str):
    files = [os.path.join(r, f)
             for r, _, fs in os.walk(root) for f in fs]

    bar = tqdm(total=len(files), desc="Converting", unit="file")
    with ThreadPoolExecutor() as pool:
        futs = {pool.submit(to_explicit_le, p): p for p in files}
        for fut in as_completed(futs):
            p, ok, how = fut.result()
            bar.set_description(f"{os.path.basename(p)} ({how})")
            bar.set_postfix(success=ok)
            bar.update()

def main():
    ap = argparse.ArgumentParser(
        description="Recursively convert DICOMs to Explicit VR Little Endian")
    ap.add_argument("path", help="Root directory to process")
    root = ap.parse_args().path

    missing = [t for t in ("dcmdjpeg", "dcmconv") if not tool_ok(t)]
    if missing:
        print(f"Error: required tool(s) not found on PATH: {', '.join(missing)}")
        print("Install DCMTK from https://dicom.offis.de/dcmtk.php.en")
        return

    os.chdir(root)
    print(f"Working in: {os.getcwd()}")
    walk_convert(os.getcwd())

if __name__ == "__main__":
    main()
