# Viltrox EF-L (Pro) custom firmware

Autofocus for EF lenses the Viltrox EF-L / EF-L Pro L-mount adapter does not know, done as a
patch on top of Viltrox's own v1.2 "For AF Lens" firmware: unknown lenses are measured once at
attach and given a focus profile instead of no profile at all.

> **Disclaimer.** This is an unofficial hobby project, not affiliated with or endorsed by
> Viltrox. It is untested on most lens/camera combinations, can leave your adapter without a
> working firmware until you re-flash the original, and voids any warranty. You flash it at your
> own risk. The repository contains no Viltrox code: you download the original firmware from
> Viltrox yourself and `build.py` patches your copy locally. MIT licence, see `LICENSE`.

1. [Files](#files)
2. [Building the firmware](#building-the-firmware)
3. [Flashing and risk](#flashing-and-risk)
4. [Compatible lenses and switch position](#compatible-lenses-and-switch-position)
5. [What the .ecp file is](#what-the-ecp-file-is)
6. [How the adapter works](#how-the-adapter-works-short-version)
7. [Variant A: auto-profile](#variant-a-auto-profile-ef-l-ver12-af-autocalecp)
8. [Variant B: table entry only](#variant-b-table-entry-only-ef-l-ver12-af-plus24-70mk1ecp)
9. [Regenerating the reverse-engineering notes](#regenerating-the-reverse-engineering-notes)
10. [Other observations](#other-observations-not-changed)

## Files

| Path | What |
|---|---|
| `build.py` | Patches your copy of the original `.ecp` into the two custom firmwares. Refuses anything but the exact v1.2 AF-lens file (SHA-256 check). |
| `src/autocal.c`, `src/link.ld` | The add-on code (variant A). ~140 lines of C, Cortex-M4. |
| `tools/ecp.py` | `.ecp` codec: unpack, pack, round-trip check. |
| `test/test_autocal.py` | Emulated self-test of the add-on against a simulated lens (needs `unicorn`). |
| `re/NOTES.md` | Map of the stock firmware: functions, globals, tables, protocol use. |
| `re/ghidra_scripts/` | Headless Ghidra scripts to regenerate a decompilation locally. |
| `LICENSE` | MIT. |

Not in the repository, by design: Viltrox's original `.ecp`, the built `.ecp` files, any decompiled output, and third-party documents. `.gitignore` keeps them out if you work in a clone.

## Building the firmware

Prerequisites: Python 3.8+, an ARM GCC toolchain (`arm-none-eabi-gcc`, e.g. the [xpack release](https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases) or your distro's package), and optionally `pip install unicorn` for the self-test.

1. Download the original firmware from Viltrox's download centre: the EF-L / EF-L PRO package **"V1.2 For AF lens"** (the "For MF lens" 2.x packages are a different firmware and will not work). Unzip and place `EF-L ver1.2 For AF Lens.ecp` in the repository root.
2. Build:
   ```
   python3 build.py                     # arm-none-eabi-gcc on PATH
   ARM_GCC=/path/to/toolchain/bin python3 build.py
   ```
   This writes `EF-L ver1.2 AF autocal.ecp` (variant A) and `EF-L ver1.2 AF plus24-70mk1.ecp` (variant B) next to the original, plus intermediates in `build/`.
3. Optional self-test of the add-on under emulation (all seven must print OK):
   ```
   python3 -m venv .venv && .venv/bin/pip install unicorn
   for s in zoom prime known mf stuck reversed detach; do .venv/bin/python test/test_autocal.py $s | tail -1; done
   ```
4. Check the codec against your original: `python3 tools/ecp.py "EF-L ver1.2 For AF Lens.ecp"` must print `ROUNDTRIP OK`.

## Flashing and risk

1. Set the adapter switch to **A**. Table lenses only autofocus in A mode; both variants target A mode (variant A also works in O mode for unknown lenses, since a profile forces the adapter path).
2. Unplug the adapter from the camera, connect USB. The `EF-L UPDATA` drive appears.
3. Copy **one** `.ecp` onto the drive, wait until the drive disappears or the LED stops, unplug.
4. Re-plug USB and check `VER 1.2.txt`: it now ends with `custom: autocal unknown lenses` or `custom: +EF24-70 2.8L mk1`. If it still says only `2021.11.24`, the bootloader rejected the file.
5. Recovery at any time: copy the original `EF-L ver1.2 For AF Lens.ecp` back the same way. The bootloader is never written by these files.

Known unknowns, in order of likelihood of biting:
* Whether the bootloader accepts a 115-block file (variant A). Rejection should be harmless (step 4 shows the old text).
* Whether the camera tolerates the 1-3 s longer lens init. If the body reports "no lens" right after mounting, half-press or power-cycle once.
* Whether each lens actually moves on `0x05`/`0x06` during init and reports a stable counter. If not, the fallback profile (1500 steps) is used and AF will be rough; the EXIF string will show `S1500`.

## Compatible lenses and switch position

Lens names are inferred from the Canon lens-ID number plus focal range stored in the firmware's tables (Canon IDs are shared between makers, so a few third-party attributions are best guesses). Any EF lens not listed below gets the auto-profile in variant A.

### Switch position A (adapter mode): 58 lenses with a stock profile

| ID | Focal | Lens |
|---|---|---|
| 29 | 50 | Canon EF 50mm f/1.8 II |
| 198 | 50 | Canon EF 50mm f/1.4 USM |
| 10 | 50 | Canon EF 50mm f/2.5 Compact Macro |
| 196 | 14 | 14mm prime reporting ID 196 (probably Samyang/Rokinon AF 14mm f/2.8 EF) |
| 161 | 17-50 | Sigma 17-50mm f/2.8 EX DC OS HSM |
| 161 | 28-75 | Tamron SP 28-75mm f/2.8 (A09) |
| 4156 | 50 | Canon EF 50mm f/1.8 STM |
| 180 | 35 | Canon EF 35mm f/1.4L USM (also what some Sigma 35mm f/1.4 Art units report) |
| 4144 | 40 | Canon EF 40mm f/2.8 STM |
| 241 | 50 | Canon EF 50mm f/1.2L USM |
| 239 | 85 | Canon EF 85mm f/1.2L II USM |
| 155 | 85 | Canon EF 85mm f/1.8 USM |
| 250 | 24 | Canon EF 24mm f/1.4L II USM |
| 254 | 100 | Canon EF 100mm f/2.8L Macro IS USM |
| 170 | 200 | Canon EF 200mm f/2.8L II USM |
| 4154 | 24 | Canon EF-S 24mm f/2.8 STM |
| 26 | 100 | Canon EF 100mm f/2.8 Macro |
| 180 | 20 | Sigma 20mm f/1.4 DG HSM Art |
| 368 | 24 | Sigma 24mm f/1.4 DG HSM Art |
| 169 | 30 | Sigma 30mm f/1.4 DC HSM Art |
| 169 | 35 | Sigma 35mm f/1.4 DG HSM Art |
| 180 | 50 | Sigma 50mm f/1.4 DG HSM Art |
| 169 | 50 | Sigma 50mm f/1.4 EX DG HSM |
| 368 | 85 | Sigma 85mm f/1.4 DG HSM Art |
| 368 | 105 | Sigma 105mm f/1.4 DG HSM Art |
| 117 | 35 | Tamron SP 35mm f/1.8 Di VC USD |
| 502 | 35 | Canon EF 35mm f/2 IS USM |
| 750 | 85 | Tamron SP 85mm f/1.8 Di VC USD |
| 254 | 90 | Tamron SP 90mm f/2.8 Di Macro VC USD |
| 246 | 16-35 | Canon EF 16-35mm f/2.8L II USM |
| 231 | 17-40 | Canon EF 17-40mm f/4L USM |
| 495 | 24-70 | Canon EF 24-70mm f/2.8L II USM |
| 237 | 24-105 | Canon EF 24-105mm f/4L IS USM |
| 752 | 24-105 | Canon EF 24-105mm f/4L IS II USM |
| 40 | 28-80 | Canon EF 28-80mm f/3.5-5.6 |
| 156 | 28-105 | Canon EF 28-105mm f/3.5-4.5 USM |
| 186 | 70-200 | Canon EF 70-200mm f/4L USM |
| 242 | 70-200 | Canon EF 70-200mm f/4L IS USM |
| 251 | 70-200 | Canon EF 70-200mm f/2.8L IS II USM |
| 489 | 70-300 | Canon EF 70-300mm f/4-5.6L IS USM |
| 238 | 70-300 | Canon EF 70-300mm f/4-5.6 IS USM |
| 36910 | 70-300 | Canon EF 70-300mm f/4-5.6 IS II USM |
| 488 | 15-85 | Canon EF-S 15-85mm f/3.5-5.6 IS USM |
| 234 | 17-85 | Canon EF-S 17-85mm f/4-5.6 IS USM |
| 4146 | 18-55 | Canon EF-S 18-55mm f/3.5-5.6 IS STM |
| 4142 | 18-135 | Canon EF-S 18-135mm f/3.5-5.6 IS STM |
| 50 | 18-200 | Canon EF-S 18-200mm f/3.5-5.6 IS |
| 4148 | 55-250 | Canon EF-S 55-250mm f/4-5.6 IS STM |
| 137 | 12-24 | Sigma 12-24mm (ID 137) |
| 112 | 18-35 | Sigma 18-35mm f/1.8 DC HSM Art |
| 174 | 70-200 | Sigma 70-200mm f/2.8 EX DG OS HSM |
| 117 | 10-24 | Tamron 10-24mm f/3.5-4.5 Di II VC HLD |
| 136 | 15-30 | Tamron SP 15-30mm f/2.8 Di VC USD |
| 117 | 18-400 | Tamron 18-400mm f/3.5-6.3 Di II VC HLD |
| 153 | 28-300 | Tamron 28-300mm f/3.5-6.3 Di VC PZD |
| 117 | 35-150 | Tamron 35-150mm f/2.8-4 Di VC OSD |
| 213 | 150-600 | Tamron SP 150-600mm (G2) |
| 160 | 11-16 | Tokina AT-X 11-16mm f/2.8 |

### Switch position A, auto-profile (variant A only)

Lenses the stock table does not know; variant A measures them at attach. Any other unlisted EF lens works the same way.

| ID | Focal | Lens |
|---|---|---|
| 230 | 24-70 | Canon EF 24-70mm f/2.8L USM (Mk I) |
| 161 | 28-70 | Canon EF 28-70mm f/2.8L USM (ID 161 is only in the stock table as 17-50 and 28-75) |
| ? | 85 | Meike 85mm F1.8 II (ID not yet known; if it clones Canon ID 155 it takes the stock EF 85 f/1.8 profile instead) |

### Switch position O (native-lens emulation): 8 lenses

In O mode the adapter pretends to be an L-mount lens. Only these have an O-mode entry; any other lens in O mode gets a generic descriptor and no stock AF (variant A gives it the auto-profile instead, which then behaves like A mode).

| ID | Focal | Lens |
|---|---|---|
| 155 | 85 | Canon EF 85mm f/1.8 USM |
| 234 | 17-85 | Canon EF-S 17-85mm f/4-5.6 IS USM |
| 161 | 17-50 | Sigma 17-50mm f/2.8 EX DC OS HSM |
| 160 | 11-16 | Tokina AT-X 11-16mm f/2.8 |
| 112 | 18-35 | Sigma 18-35mm f/1.8 DC HSM Art |
| 137 | 10-20 | Sigma 10-20mm |
| 368 | 85 | Sigma 85mm f/1.4 DG HSM Art (emulated as the L-mount "85mm F1.4 DG HSM Art 016") |
| 180 | 50 | Sigma 50mm f/1.4 DG HSM Art (emulated as the L-mount "50mm F1.4 DG HSM Art 014") |

## What the `.ecp` file is

* `0x000` copyright string, `0x064` three little-endian u32: total length (`0xE200`), app length (`0xD6D8`), version (`0x12` = 1.2). Padded with `0xFF` to 73728 bytes.
* From `0x200`: 112 blocks of 512 bytes. Each block = `"_Best->\0"` + u32 block index + 500 data bytes.
* Data obfuscation per 32-bit little-endian word: `plain = bswap32(rol32(cipher, 1))`. No encryption, no checksum.
* Block 0 = FAT directory entry + text of the `VER 1.2.txt` file the bootloader shows. Block 1 = empty. Blocks 2..111 = the application, contiguous, loaded at **0x08020400**.
* MCU: STM32F4 (84 MHz timers, RCC at 0x40023800, 128 KB RAM). Bootloader occupies sectors 0-4; app is in sector 5. USB VID:PID `0483:572a` is the STM32Cube mass-storage example, the bootloader enters it by itself when powered from USB (the app never requests it), so a bad app can always be replaced by copying a `.ecp` onto the drive again.

`python3 tools/ecp.py file.ecp` decodes and re-encodes and must print `ROUNDTRIP OK`.

## How the adapter works (short version)

* **Lens side**: USART1 in synchronous mode = Canon EF bus (bytes bit-reversed, 100 kHz, 500 kHz if the lens advertises it). TIM2 paces one byte per tick; a queue of tiny "step" functions (one per protocol byte) runs from the TIM2 interrupt.
* **Camera side**: SPI1 slave + DMA2, TIM4 for the sync line, PB6/PB7 as handshake lines. The adapter identifies itself to the body either as an adapter ("LDAFRP", switch position A) or as a native lens ("LDAFR!", switch position O, which emulates a few Sigma Art L-mount lenses).
* At lens attach the firmware reads the EF lens ID (`0x80` command), focal range, aperture (`0xB0`), name (`0x82`), then looks the lens up in a table of **58 lenses (A mode)** or **8 lenses (O mode)** by `(lens ID, min focal, max focal)`.
* A table hit loads a **profile**: distance (cm) vs focus-counter table, total focus steps, focal-length list for zooms, flags. The profile is what the body is told about the lens and what every absolute focus move is computed from.
* **A lens that is not in the table gets no profile**: the step tables stay empty, the advertised focus range is zero, and the body's focus requests produce nothing. That is the "no autofocus at all" you see with the 24-70 Mk I (Canon ID 230; only the Mk II, ID 495, is in the table). The Sigma 35 Art (ID 150) and the Meike are not in the table either.

## Variant A: auto-profile (`EF-L ver1.2 AF autocal.ecp`)

The last step of the lens-initialisation sequence is replaced by `autocal_step()` (`src/autocal.c`):

1. Lens found in the table: behaves exactly like the original firmware.
2. Lens not found: drives the focus to the near end (`0x06`), waits until the focus counter (`0xC0`) stops changing, reads the near distance from the lens if it has a distance encoder (`0xC2`), drives to infinity (`0x05`), reads the counter again. Each leg times out after 3 s.
3. Builds a profile from the measured step range: Viltrox's own generic 9-point distance curve scaled to the lens's near limit (or 10x the focal length if the lens has no encoder), a 1/distance step distribution, and a 20-point focal list for zooms. Then hands it to the firmware's normal profile loader, so from here on the lens is handled like any table lens.
4. Writes diagnostics into the lens name the camera records in EXIF: `EF24-70mm #E600 S3000 D38` means lens ID key `E600`, 3000 measured focus steps, near limit 38 cm. Trailing letters: `!` fallback step count, `M` lens was in MF/busy, `T` a sweep leg timed out, `R` counter direction reversed, `E` near limit estimated (lens has no distance encoder; normal for many lenses). If the lens reports its own name, the suffix is appended to it. **Please send me this string for each lens you try.**

Safety guards (added on request, on top of the firmware's own behaviour, which has none):
* Reads lens status (`0x90`) before moving anything. If the lens's AF/MF switch is on MF or the lens reports busy/error, no sweep is done and a fallback profile is used (EXIF suffix `!M`).
* Each sweep leg has a 3 s timeout; on timeout the motor is stopped (`0x07`) before the next command (`T`).
* Measured step range is accepted only between 200 and 20000 counts and only if the counter runs the same direction as every stock profile assumes (`R` flags the opposite). The near limit is accepted between 10 cm and 30 m; without a distance encoder it is estimated as 10x the focal length within the same clamps (`E`). Anything implausible falls back to a 1500-step generic profile (`!`). The camera is never given a zero, wrapped or negative range.
* The step re-checks that the lens is still present on every call, so a lens pulled mid-sweep cannot leave a half-finished calibration to replay onto the next lens. Position tracking is only told "parked at infinity" when the infinity leg actually completed.
* The sweep sends the AF-speed command (`0x50`) and then the lens's own end-seeking commands (`0x06`/`0x05`), the same byte sequence the stock firmware uses for its focus moves and its post-attach move to infinity. The lens terminates these at its stops itself; no raw step moves are issued during calibration.
* Lenses without `0x80` lens info, and all table lenses, take the original code path untouched.
* The add-on's RAM lives at 0x20007440, directly above the firmware's stack top, present on every STM32F4 variant.

Costs: lens initialisation takes about 1-3 s longer the first time a lens is attached (the lens racks to both ends once). The image is 1500 bytes longer than the original (115 blocks instead of 112); the header fields are updated accordingly. I believe the bootloader simply writes what it receives, but this is the one thing about variant A I could not verify, hence variant B.

## Variant B: table entry only (`EF-L ver1.2 AF plus24-70mk1.ecp`)

Same size and block count as the original. Adds the EF 24-70 f/2.8L Mk I to the A-mode table pointing at the 24-70 II's profile (6818 steps, 38 cm near limit, 24-70 focal list). If the Mk I's real step count differs, AF will still be closed-loop but may overshoot or be slower. Does nothing for the Meike or the Sigma 35.

## Regenerating the reverse-engineering notes

`re/NOTES.md` refers to functions by address in a Ghidra decompilation that is not shipped. To recreate it: run `build.py` once (it writes the decoded stock image to `build/app_orig_0x08020400.bin`), then with Ghidra 11+:

```
analyzeHeadless /tmp/gproj efl -import build/app_orig_0x08020400.bin -loader BinaryLoader \
  -loader-baseAddr 0x08020400 -processor ARM:LE:32:Cortex -scriptPath re/ghidra_scripts \
  -preScript ReadOnly.java -preScript SeedVectors.java -postScript FillGaps.java \
  -postScript ExportAll.java /abs/path/to/outdir
```

The best public reference for the Canon EF lens bus is J.P.'s "EF Lens Protocol" document (2016, French), linked from the eddyem/canon-lens repository on GitHub.

## Other observations (not changed)

* The choice between the `0x90` and `0x91` status command is made from a profile flag *before* the profile is loaded, so it always uses the previous lens's flag (`FUN_080215f0` default case). Harmless for lenses without IS; worth fixing if an IS lens misbehaves.
* Unknown lenses in O mode get a 5-entry generic descriptor and no AF by design; variant A changes that by giving them a profile.
* Lens names are only read when the lens supports the `0x82` command; older lenses therefore show up with an empty name in EXIF. Variant A synthesises `EF<min>-<max>mm` for them.
* The firmware has no checksum or signature on the image; the bootloader presumably checks only the `_Best->` magic and block indices.
