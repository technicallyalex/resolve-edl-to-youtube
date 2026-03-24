# Resolve EDL to YouTube Chapters

Convert DaVinci Resolve timeline marker EDL exports into YouTube chapter timestamps.

This project includes a Windows GUI app and a portable `.exe` build. It is meant for editors who already export timeline markers from Resolve and want clean chapter lines like:

```text
0:00 Intro
0:13 Battlefield
1:44 DLSS 5
```

## What It Does

- Loads a DaVinci Resolve marker EDL file
- Parses timeline marker positions into YouTube timestamp format
- Uses marker names or marker comments as chapter titles
- Optionally prepends a `0:00` chapter like `Intro`
- Lets you copy the generated chapters to the clipboard
- Lets you save the generated chapters to a plain text file

## Included Files

- `ResolveEdlToYouTubeChapters.exe`
  Portable Windows build for end users
- `resolve_edl_to_youtube_gui.py`
  Python source for the GUI app
- `build_portable_exe.bat`
  Rebuild script for the portable `.exe`

## Recommended Use

Most people should just use the portable executable:

1. Download `ResolveEdlToYouTubeChapters.exe`
2. Run it
3. Click `Browse` and select your Resolve marker `.edl` file
4. The file loads automatically
5. Adjust options if needed
6. Click `Generate Chapters`
7. Use `Copy to Clipboard` or `Save as Text File`

## Input Format

The app is built for DaVinci Resolve timeline marker EDL exports, including marker lines in formats like:

```text
|C:ResolveColorBlue |M:Battlefield |D:1
```

and older `MARKER:` style lines.

## Options

- `FPS`
  Timeline frame rate used to interpret timecode
- `Use marker comments`
  Uses the marker comment instead of the marker name
- `Dedupe consecutive lines`
  Removes repeated adjacent chapter lines
- `Prepend 0:00 title`
  Adds a first chapter at `0:00` when the first marker starts later

## Launching With a File Path

The app can also open an EDL file directly from the command line:

```powershell
.\ResolveEdlToYouTubeChapters.exe "C:\path\to\Edit.edl"
```

## Running the Python Version

If you want to run the source instead of the `.exe`:

```powershell
python .\resolve_edl_to_youtube_gui.py
```

You can also pass an EDL file path:

```powershell
python .\resolve_edl_to_youtube_gui.py "C:\path\to\Edit.edl"
```

## Building the Portable EXE

To rebuild the executable from source:

```powershell
.\build_portable_exe.bat
```

This project was built and packaged on Windows.

## Notes

- The app is designed for Windows
- The `.exe` is intended to be portable and run without a separate Python install
- If Resolve changes its EDL marker export format in the future, the parser may need updates

## Repo Purpose

This repository exists so people can:

- download a ready-to-run Windows executable
- inspect the Python source
- rebuild the executable themselves
- adapt the parser for their own Resolve workflow
