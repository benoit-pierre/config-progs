#! /bin/sh

dry_run=0
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

# ConsoleKit support. {{{

cs_action()
{
  run dbus-send \
  --system --dest=org.freedesktop.ConsoleKit \
  --type=method_call --print-reply --reply-timeout=2000 \
  /org/freedesktop/ConsoleKit/Manager \
  "org.freedesktop.ConsoleKit.Manager.$1"
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
  *)
    exit 2
    ;;
esac

# vim: foldmethod=marker
