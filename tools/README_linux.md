# Linux UpgradeDownload rebuild

`upgrade_download_linux.py` is a Linux-native replacement/orchestrator for the
Windows-only `UpgradeDownload.exe` flow.

## Features

- Reads existing `Bin/UpgradeDownload.ini` settings.
- Reconstructs partition flash plan from the selected `PAC_*` section.
- Sends the same initial ROM sync byte (`0x7E`) seen in vendor logs.
- Optionally extracts PAC archives using an external extractor.
- Delegates flashing to an external Linux tool (`spd_dump`-style interface).

## Quick start

```bash
./install-linux.sh ~/.local/bin
python3 -m pip install --user -r requirements-linux.txt

# alternatively run directly from repo:
python3 tools/upgrade_download_linux.py --show-plan
python3 tools/upgrade_download_linux.py --probe /dev/ttyUSB0 --timeout 2
python3 tools/upgrade_download_linux.py --probe-usb 1782:4d00
python3 tools/upgrade_download_linux.py --probe /dev/ttyUSB0 --flash --flasher spd_dump
python3 tools/upgrade_download_linux.py --probe-usb 1782:4d00 --flash --flasher spd_dump
```

## Notes

- For serial probing install: `pip install pyserial`.
- For PAC extraction install an extractor such as `p7zip` (`7z`).
- Proprietary command packets used for full FDL download in
  `UpgradeDownload.exe` live in vendor DLLs; this rebuild keeps compatibility by
  delegating the final transport to an external Linux flasher.
