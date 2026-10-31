# Resolve EDL to YouTube Chapters

Convert DaVinci Resolve timeline marker EDL exports into YouTube chapter timestamps.

This project provides a Windows desktop app and a portable `.exe` for editors who want to turn Resolve timeline markers into clean YouTube chapter lines such as:

```text
0:00 Intro
0:13 Battlefield
1:44 DLSS 5
```

## Current Release

Latest release:
- [`v1.0.1 - UI and workflow improvements`](https://github.com/technicallyalex/resolve-edl-to-youtube/releases/tag/v1.0.1)

Download:
- `ResolveEdlToYouTubeChapters.exe` from the repo's Releases page

## What The App Does

- Loads DaVinci Resolve marker EDL files
- Converts timeline marker positions into YouTube timestamp format
- Uses marker names or marker comments as chapter titles
- Optionally prepends a synthetic `0:00` chapter
- Copies generated chapters to the clipboard
- Exports generated chapters to a plain text file

## Current App Behavior

- Selecting an `.edl` file automatically loads it and generates chapters
- Editing options automatically refreshes the chapter output
- The app can be launched with an EDL path argument
- The default display mode is `Light`
- A `View` menu lets you switch between `Light`, `Dark`, and `System`
- Thin scrollbars auto-hide unless content overflows
- The status area only appears when there is something to report

## Included Files

- `ResolveEdlToYouTubeChapters.exe`
  Portable Windows build for end users
- `resolve_edl_to_youtube_gui.py`
  Python source for the GUI app
- `build_portable_exe.bat`
  Rebuild script for the portable executable

## Recommended Use

For most users:

1. Download `ResolveEdlToYouTubeChapters.exe` from Releases.
2. Run the app.
3. Click `Browse` and select your Resolve marker `.edl` file.
4. The file loads and chapters generate automatically.
5. Adjust options if needed.
6. Use `Copy to Clipboard` or `Save as Text File`.

## Supported Input

The app is built for DaVinci Resolve timeline marker EDL exports, including marker lines such as:

```text
|C:ResolveColorBlue |M:Battlefield |D:1
```

It also supports older `MARKER:` style lines.

## Options

- `FPS`
  Timeline frame rate used to interpret timecode
- `Use marker comments`
  Uses the marker comment instead of the marker name
- `Dedupe consecutive lines`
  Removes repeated adjacent chapter lines
- `Prepend 0:00 chapter`
  Adds a synthetic first chapter when the first marker starts later
- `Intro` title field
  Sets the label used for the synthetic `0:00` chapter

## Display Modes

From the menu bar:

- `View > Light`
- `View > Dark`
- `View > System`

`System` follows the Windows app theme setting while the app is running.

## Launching With a File Path

The app can open an EDL directly from the command line:

```powershell
.\ResolveEdlToYouTubeChapters.exe "C:\path\to\Edit.edl"
```

## Running From Python

Run the source version:

```powershell
python .\resolve_edl_to_youtube_gui.py
```

Or pass an EDL file path:

```powershell
python .\resolve_edl_to_youtube_gui.py "C:\path\to\Edit.edl"
```

## Building The Portable EXE

To rebuild the Windows executable:

```powershell
.\build_portable_exe.bat
```

## Notes

- Built for Windows
- Designed for DaVinci Resolve timeline marker EDL exports
- Portable single-file executable
- The app includes custom Tcl/Tk packaging support for reliable Windows builds
- If Resolve changes its EDL marker export format, the parser may need updates

## Repo Purpose

This repository exists so people can:

- download a ready-to-run Windows executable
- inspect the Python source
- rebuild the executable themselves
- adapt the parser for their own Resolve workflow under the [MIT license](LICENSE)

## AI disclosure

The maintainer confirmed on 2026-10-31 that ChatGPT was used for this project. The available records do not establish the specific tasks, affected files, model versions, or proportion of AI-generated material.

OpenAI Codex was used for the 2026-10-31 repository audit and to draft these disclosure and licensing documentation changes. This describes this audit only and does not establish earlier Codex use.

## License and third-party components

The project's source and documentation are [MIT licensed](LICENSE). You may modify, fork and redistribute covered material under those terms. Keep the copyright notice, including the original repository URL, and the permission notice with copies or substantial portions.

Python, Tcl/Tk, PyInstaller-related files and other components in the portable executable retain their own terms. The MIT license does not relicense them or grant rights to DaVinci Resolve, YouTube, third-party trademarks, or your input media. See [dependency, attribution and build-provenance notes](docs/THIRD_PARTY_NOTICES.md).

The checked-in build script references `runtime_tkinter.py` and a `hooks/` directory that are absent from the reviewed repository. It also upgrades PyInstaller without pinning a version. The published executable cannot currently be reproduced solely from these checked-in build materials; its complete dependency versions and notice coverage remain unresolved.
