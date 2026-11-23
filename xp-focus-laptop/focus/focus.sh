#!/bin/sh
# The "focus" command for the Cygwin terminal.
# Install or update it with:
#     cp /cygdrive/c/focus/focus.sh /usr/bin/focus && chmod +x /usr/bin/focus
PSPI="${FOCUS_PSPI:-pi@169.254.55.1}"

if [ "$1" = "sync" ]; then
    tmp="/tmp/focus-inbox.$$"
    echo "Fetching notes from the PSPi ($PSPI) ..."
    # One connection: print the inbox, keep a copy on the PSPi, then empty it.
    if ssh -o ConnectTimeout=8 "$PSPI" \
        'touch ~/focus-inbox.txt; cat ~/focus-inbox.txt; cat ~/focus-inbox.txt >> ~/focus-inbox.done; : > ~/focus-inbox.txt' > "$tmp"
    then
        python C:/focus/focus.py inbox "$(cygpath -w "$tmp")"
    else
        echo "Could not reach the PSPi. Is it plugged in and finished booting?"
    fi
    rm -f "$tmp"
    exit 0
fi

exec python C:/focus/focus.py "$@"
