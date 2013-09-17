#! /bin/sh

cs_action()
{
  dbus-send \
  --system --dest=org.freedesktop.ConsoleKit \
  --type=method_call --print-reply --reply-timeout=2000 \
  /org/freedesktop/ConsoleKit/Manager \
  "org.freedesktop.ConsoleKit.Manager.$1"
}

reboot()
{
  echo 'rebooting'
  cs_action Restart
}

halt()
{
  echo 'shutting down'
  cs_action Stop
}

case "$1" in
  -r) reboot ;;
  -h|'') halt ;;
  *) exit 2 ;;
esac
