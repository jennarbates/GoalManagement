CONNECTING THE XP LAPTOP TO THE PSPi OVER USB
=============================================

Copy this 8-pspi-usb folder to C:\xp-focus-kit on the laptop first.

1. INSTALL THE DRIVER (once)
   - Plug the PSPi into the laptop and let it boot.
   - Start > Run > devmgmt.msc
   - Right-click the device with the yellow mark > Update Driver.
   - "Can Windows connect to Windows Update?"  ->  No, not this time.
   - "Install from a list or specific location (Advanced)".
   - "Don't search. I will choose the driver to install."
   - If asked for a hardware type, pick "Network adapters".
   - Click "Have Disk", browse to C:\xp-focus-kit\8-pspi-usb,
     pick pspi-usb.inf, OK.
   - Choose "PSPi USB Network Gadget", Next.
   - At the "has not passed Windows Logo testing" warning,
     click Continue Anyway.

2. GIVE THE LAPTOP A FIXED ADDRESS (once)
   - Start > Run > ncpa.cpl
   - Right-click the new "Local Area Connection" whose description
     says PSPi USB Network Gadget > Properties.
   - Select "Internet Protocol (TCP/IP)" > Properties.
   - "Use the following IP address":
         IP address:   169.254.55.2
         Subnet mask:  255.255.0.0
     Leave gateway and DNS empty. OK, Close.

3. TEST
   - Start > Run > cmd
         ping 169.254.55.1
     You should see "Reply from 169.254.55.1".

4. CONNECT
   - In the Cygwin terminal (if it has ssh):
         ssh pi@169.254.55.1
   - Or with PuTTY: Host Name 169.254.55.1, Port 22, Open,
     then log in as pi.

IF THE DEVICE SHOWS "CANNOT START (CODE 10)" AFTER STEP 1
   The PSPi is not offering the Windows (RNDIS) mode. Note it down;
   the fix is a setting on the PSPi side, not on the laptop.
