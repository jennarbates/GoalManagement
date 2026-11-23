NOTES ON THE PSPi -> PARKING LOT ON THE LAPTOP
==============================================

One-time install (PSPi plugged into the laptop, in the Cygwin terminal):
    scp /cygdrive/c/focus/pspi/note pi@169.254.55.1:
    ssh -t pi@169.254.55.1 "sudo install -m 755 note /usr/local/bin/note"
    cp /cygdrive/c/focus/focus.sh /usr/bin/focus && chmod +x /usr/bin/focus

On the PSPi, any time:
    note look up hash maps        saves the line in ~/focus-inbox.txt
    note -l                       shows what is waiting

On the laptop, when the PSPi is plugged in:
    focus sync
  This pulls the notes into park.txt and empties the PSPi inbox.
  A copy stays on the PSPi in ~/focus-inbox.done in case anything goes wrong.
  The notes are then sorted at the end of your next focus day, like any
  other parked thought.
