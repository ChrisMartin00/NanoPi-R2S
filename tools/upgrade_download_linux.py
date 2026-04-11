#!/usr/bin/env python3
"""Linux replacement orchestrator for Unisoc UpgradeDownload workflow.

This tool reconstructs the observable UpgradeDownload flow:
- parse UpgradeDownload.ini
- optional PAC extraction with an external tool
- serial ROM sync probe (0x7E handshake)
- partition flash plan generation and delegation to an external flasher

It is intentionally modular: vendor proprietary packet encoding is not re-used.
"""

from __future__ import annotations

import argparse
import configparser
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class PartitionEntry:
    file_id: str
    enabled: bool
    path: str


def load_ini(path: Path) -> configparser.ConfigParser:
    if not path.exists():
        raise FileNotFoundError(f"INI not found: {path}")
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    text = path.read_text(encoding="utf-8", errors="ignore")
    cfg.read_string(text)
    return cfg


def selected_product(cfg: configparser.ConfigParser) -> str:
    return cfg.get("Selection", "SelectProduct", fallback="").strip()


def parse_partitions(cfg: configparser.ConfigParser) -> List[PartitionEntry]:
    product = selected_product(cfg)
    if not product or product not in cfg:
        return []
    parts: List[PartitionEntry] = []
    for file_id, raw in cfg[product].items():
        enabled = False
        file_path = ""
        token = raw.strip()
        if "@" in token:
            left, right = token.split("@", 1)
            enabled = left.strip() == "1"
            file_path = right.strip()
        parts.append(PartitionEntry(file_id=file_id.strip(), enabled=enabled, path=file_path))
    return parts


def print_plan(entries: Iterable[PartitionEntry]) -> None:
    print("Flash plan:")
    for e in entries:
        status = "ON " if e.enabled else "OFF"
        src = e.path if e.path else "<none>"
        print(f"  [{status}] {e.file_id:16s} -> {src}")


def extract_pac(pac: Path, out_dir: Path, extractor: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [extractor, "x", str(pac), f"-o{out_dir}"] if extractor.endswith("7z") else [extractor, str(pac), "-o", str(out_dir)]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def probe_serial(port: str, baud: int, timeout: float) -> bool:
    try:
        import serial  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pyserial is required for --probe") from exc

    with serial.Serial(port=port, baudrate=baud, timeout=timeout) as ser:
        ser.reset_input_buffer()
        ser.write(b"\x7e")
        ser.flush()
        deadline = time.time() + timeout
        while time.time() < deadline:
            data = ser.read(64)
            if data:
                print(f"RX ({len(data)}B): {data.hex(' ')}")
                return True
    return False


def probe_usb(vidpid: str) -> bool:
    if not re.fullmatch(r"[0-9a-fA-F]{4}:[0-9a-fA-F]{4}", vidpid):
        raise RuntimeError("Invalid VID:PID format, expected like 1782:4d00")
    lsusb = shutil.which("lsusb")
    if lsusb is None:
        raise RuntimeError("lsusb not found; install usbutils")
    cp = subprocess.run([lsusb], capture_output=True, text=True, check=True)
    pat = vidpid.lower()
    for line in cp.stdout.splitlines():
        if pat in line.lower():
            print(f"USB device found: {line}")
            return True
    return False


def build_external_flash_cmd(
    flasher: str,
    port: str,
    baud: int,
    entries: Iterable[PartitionEntry],
    skip_ids: set[str],
) -> List[str]:
    cmd: List[str] = [flasher, "--port", port, "--baud", str(baud)]
    for e in entries:
        if not e.enabled or not e.path or e.file_id in skip_ids:
            continue
        cmd.extend(["--part", f"{e.file_id}={e.path}"])
    return cmd


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Linux UpgradeDownload-compatible orchestrator")
    ap.add_argument("--ini", default="Bin/UpgradeDownload.ini", help="Path to UpgradeDownload.ini")
    ap.add_argument("--show-plan", action="store_true", help="Print parsed flash plan and exit")
    ap.add_argument("--probe", metavar="/dev/ttyUSB0", help="Probe ROM handshake on serial port")
    ap.add_argument("--probe-usb", metavar="VID:PID", help="Probe for USB device, e.g. 1782:4d00")
    ap.add_argument("--timeout", type=float, default=1.0, help="Probe timeout seconds")
    ap.add_argument("--extract-pac", metavar="file.pac", help="Extract PAC using external extractor")
    ap.add_argument("--extractor", default="7z", help="Extractor command (default: 7z)")
    ap.add_argument("--out", default="./pac_unpacked", help="PAC extraction output directory")
    ap.add_argument("--flash", action="store_true", help="Invoke external Linux flasher")
    ap.add_argument("--flasher", default="spd_dump", help="External flasher command")
    ap.add_argument("--skip", default="", help="Comma-separated file IDs to skip")

    ns = ap.parse_args(argv)

    cfg = load_ini(Path(ns.ini))
    baud = int(cfg.get("Serial port", "Baud rate", fallback="460800"))
    entries = parse_partitions(cfg)

    if ns.show_plan:
        print(f"Selected product: {selected_product(cfg) or '<unset>'}")
        print_plan(entries)

    if ns.extract_pac:
        extractor = shutil.which(ns.extractor)
        if extractor is None:
            raise RuntimeError(f"Extractor not found in PATH: {ns.extractor}")
        extract_pac(Path(ns.extract_pac), Path(ns.out), extractor)

    if ns.probe:
        ok = probe_serial(ns.probe, baud=baud, timeout=ns.timeout)
        if ok:
            print("ROM sync probe: OK")
        else:
            print("ROM sync probe: no response")
            return 2

    if ns.probe_usb:
        ok = probe_usb(ns.probe_usb)
        if ok:
            print("USB probe: OK")
        else:
            print("USB probe: not found")
            return 2

    if ns.flash:
        if not ns.probe and not ns.probe_usb:
            raise RuntimeError("--flash requires --probe PORT or --probe-usb VID:PID")
        flasher = shutil.which(ns.flasher) or ns.flasher
        skip_ids = {s.strip() for s in ns.skip.split(",") if s.strip()}
        cmd = build_external_flash_cmd(flasher, ns.probe, baud, entries, skip_ids)
        print("Launching external flasher:")
        print(" ".join(cmd))
        subprocess.run(cmd, check=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
