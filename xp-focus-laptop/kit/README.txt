XP FOCUS KIT - HP Compaq nc2400 (Windows XP SP3)
================================================

Copy this whole folder to a FAT32 USB stick (needs about 160 MB free),
then on the laptop copy it to C:\kit and install from there.

BEFORE INSTALLING
  Turn off USB autorun and uninstall the old work software
  (OpenVPN, SonicWALL VPN, Citrix, Google Earth, Windows Live,
  Java Update, Adobe updater) from Control Panel > Add or Remove Programs.

INSTALL IN THIS ORDER (double-click each file, accept the defaults
unless noted)

  7-7zip\7z1604.exe
      Opens zip and other archives.

  1-python\python-3.4.4.msi
      NOTE: on the "Customize" screen, set "Add python.exe to Path"
      to "Will be installed on local hard drive".
      Test: Start > Run > cmd, then type:  python --version

  2-c-compiler\tdm-gcc-5.1.0-3.exe
      Click "Create", choose "MinGW/TDM (32-bit)".
      UNTICK "Check for updated files on the TDM-GCC server".
      Test: open a NEW cmd window, type:  gcc --version
      (Skip this one if "gcc --version" already works in Cygwin
      and you are happy using the Cygwin terminal.)

  3-notepad++\npp.7.9.2.Installer.exe
      Code editor for Python and C. Decline any update prompts.

  4-sumatrapdf\SumatraPDF-3.1.2-install.exe
      PDF reader.

  5-anki\anki-2.0.52.exe
      Flashcards. Skip the AnkiWeb sync/login - it works offline.

  6-vlc\vlc-3.0.20-win32.exe
      Music and video. On first run, untick both network options.

  9-putty\putty.exe  (and pscp.exe)
      SSH client, version 0.83. Nothing to install: copy the
      9-putty folder to C:\ and double-click putty.exe.
      pscp.exe copies files to and from the PSPi from cmd.

  8-pspi-usb
      Driver file and steps for reaching the PSPi over USB.
      See README-pspi.txt inside that folder.

FIRST PROGRAMS
  Python:   save as hello.py   containing   print("hello")
            run with:  python hello.py
            (Python 3.4 has no f-strings; use "{}".format(x))
  C:        save as hello.c, then:
            gcc hello.c -o hello.exe
            hello.exe

GOING OFFLINE (after everything is installed)
  Right-click My Computer > Manage > Device Manager.
  Right-click > Disable each of:
    Network adapters:  Intel PRO/Wireless 3945ABG
                       Broadcom NetLink Gigabit Ethernet
                       1394 Net Adapter
    Modems:            HDAUDIO Soft Data Fax Modem
    Bluetooth devices: everything listed

CHECKSUMS (SHA-256) are in checksums.txt
