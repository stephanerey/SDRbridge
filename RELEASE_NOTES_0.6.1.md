# SDRbridge 0.6.1

SDRbridge 0.6.1 is a visual identity patch on top of version 0.6.0.

## Changes

- new SDRbridge icon designed to remain recognizable from 16×16 through
  256×256 pixels;
- icon embedded in the Windows executable and Qt application;
- matching icon for the taskbar, Start menu, desktop shortcut, installer, and
  uninstaller entry;
- explicit Windows application identity for stable taskbar pinning;
- English README shown by default on GitHub, with a complete French README and
  first-line language links in both directions.

All receiver, DSP, client, capture, and hardware-support behavior remains
unchanged from version 0.6.0. The installer contains the private
`SoapySDRPlay3` module; SDRplay remains the only radio hardware supported out
of the box.

## Verification

- 91/91 automated tests passed;
- executable and installer icon resources extracted and visually verified;
- isolated silent install, installed executable probe, and uninstall passed.

Installer SHA-256:
`4875EF238FE9219C8AAADF9ECACDBECAEE83463A3C7BEE0120DFDD834059C9FB`

The installer is not digitally signed. Windows SmartScreen may therefore show
a warning.
