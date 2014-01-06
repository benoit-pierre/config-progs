#! /bin/sh

dry_run="${SHUTDOWN_DRYRUN-0}"
mode=''

run()
{
  if [ 0 -eq $dry_run ]
  then
    "$@"
  else
    echo "$@"
  fi
}

# DBus helper.
dbus()
{
  dest="$1"
  obj="/`echo "$1$2" | tr . /`"
  if="$1$2.$3"

  run dbus-send \
  --system --print-reply \
  --dest="$dest" \
  "$obj" "$if"
}

# ConsoleKit support. {{{

cs_action()
{
  dbus org.freedesktop.ConsoleKit .Manager "$1"
}

cs_reboot()
{
  cs_action Restart
}

cs_halt()
{
  cs_action Stop
}

# }}}

# systemd support. {{{

sd_reboot()
{
  run systemctl reboot
}

sd_halt()
{
  run systemctl poweroff
}

# }}}

# suspend/hibernate support. {{{

pm_action()
{
  dbus org.freedesktop.UPower '' "$1"
}

suspend()
{
  pm_action Suspend
}

hibernate()
{
  pm_action Hibernate
}

# }}}

if which systemctl >/dev/null 2>&1
then
  mode='sd'
else
  mode='cs'
fi

case "$1" in
  -h|'')
  echo 'shutting down'
    "$mode"_halt
    ;;
  -r)
  echo 'rebooting'
    "$mode"_reboot
    ;;
  -s)
    echo 'suspending'
    suspend
    ;;
  -S)
    echo 'hibernating'
    hibernate
    ;;
  *)
    exit 2
    ;;
esac

# vim: foldmethod=marker
