# UpgradeDownload.exe reverse-engineering notes

This repository ships Windows-only binaries (`UpgradeDownload.exe`, `CmdDloader.exe`) for flashing Unisoc/Spreadtrum devices.

## What was reverse engineered

Using `objdump` and `strings` on `Bin/UpgradeDownload.exe`:

- Binary type: 32-bit PE GUI executable (timestamp 2020-01-21).
- Important imported vendor DLL interfaces:
  - `SecBinPack9.dll` (`CreateSecPacParse`) for PAC parsing.
  - `PortHound.dll` (`CreateDevHound`) for serial/USB device detection.
  - `ProcessFlow.dll` for process/MES integration.
- Embedded CLI/flow strings indicate these operations exist:
  - `Load PAC file successfully!`
  - `CheckBaud`, `ConnectRom`, `FDL1`, `FDL2`, `REPARTITION`, `Download`, `ReadPartition`, `ReadChipUID`, `CHECK_NV`.
- Embedded usage string:
  - `Usage: ResearchDownload.exe <pac path> <product version>`

From `Bin/UpgradeDownload.ini` + archived command logs:

- The default UART baud is `460800` and the initial ROM sync writes a single byte `0x7E`.
- Tool sequence inferred from logs:
  1. Open/download channel.
  2. Set CRC mode.
  3. Connect to ROM (`ConnectRom`) with 0x7E sync.
  4. Upload FDL stages and flash listed partitions from PAC unpack output.

## Linux rebuild strategy

A native Linux rewrite is provided at `tools/upgrade_download_linux.py`.

It intentionally focuses on *observable behavior* and *interoperability*:

1. Parse existing `UpgradeDownload.ini` files.
2. Optionally extract `.pac` with an external extractor (`7z` / `unar` / etc).
3. Perform the same UART ROM sync handshake (`0x7E`).
4. Generate and execute a flash plan by delegating to an external Linux flasher
   (`spd_dump`/`unisoc_dloader` compatible command), because the proprietary
   command packet set for `FDL1/FDL2/REPARTITION/...` is implemented inside
   vendor DLLs not shipped with source.

This gives a practical Linux path while keeping compatibility with existing
project config and artifact layout.
