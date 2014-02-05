#!/bin/sh

# X11 keyboard configuration.

verbose=0
test_loop=0
lang='colemak'

while [ 0 -ne $# ]
do
  case "$1" in
    -v)
      verbose=1
      ;;
    -t)
      test_loop=1
      ;;
    -*)
      echo 2>&1 "setxkbd: unsupported option: $1"
      exit 1
      ;;
    *)
      lang="$1"
      ;;
  esac
  shift
done

setxkbd()
{
  type="$1"
  id="$2"
  layout="$3"
  variant="$4"
  options="$5"
  xkbdir="${XDG_CONFIG_HOME:-$HOME/.config}/x11/xkb"

  [ 0 -ne $verbose ] && printf 'setxkbd: %2u [%-40s]: %s|%s|%s\n' "$id" "$type" "$layout" "$variant" "$options"

  setxkbmap -layout "$layout" -variant "$variant" -option -option "$options" -print |
  sed 's/"pc+\(.*\)+inet(evdev)\([^"]*\)"\s*};$/"pc+inet(evdev)+\1\2" };/' |
  xkbcomp -w0 -I"$xkbdir" ${id:+-i "$id"} - "$DISPLAY"
}

setxkbd general '' bpierre "$lang" compose:rwin

xinput list |
# ⎡ Virtual core pointer                          id=2    [master pointer  (3)]
# ⎜   ↳ Virtual core XTEST pointer                id=4    [slave  pointer  (2)]
# ⎜   ↳ Xephyr virtual mouse                      id=7    [slave  pointer  (2)]
# ⎜   ↳ TypeMatrix.com USB Keyboard               id=9    [slave  pointer  (2)]
# ⎜   ↳ Logitech USB Optical Mouse                id=12   [slave  pointer  (2)]
# ⎣ Virtual core keyboard                         id=3    [master keyboard (2)]
#     ↳ Virtual core XTEST keyboard               id=5    [slave  keyboard (3)]
#     ↳ Xephyr virtual keyboard                   id=6    [slave  keyboard (3)]
#     ↳ Power Button                              id=6    [slave  keyboard (3)]
#     ↳ Power Button                              id=7    [slave  keyboard (3)]
#     ↳ TypeMatrix.com USB Keyboard               id=8    [slave  keyboard (3)]
#     ↳ Logitech USB Keyboard                     id=10   [slave  keyboard (3)]
#     ↳ Logitech USB Keyboard                     id=11   [slave  keyboard (3)]
#    ↳ TypeMatrix.com USB Keyboard               id=8    [slave  keyboard (3)]
sed -n 's/^\s\+↳\s\+\(\<.\+\>\) [Kk]eyboard\s\+.*id=\([0-9]\+\)\s\+\[slave \+keyboard ([0-9]\+)\]$/\2 \1/p' |
while read id type
do
  case "$type" in
    'Virtual core XTEST')
      ;;
    'TypeMatrix.com'*)
      setxkbd "$type" "$id" bpierre "$lang"_typematrix
      ;;
    'Xephyr virtual')
      setxkbd "$type" "$id" bpierre "$lang" compose:rwin
      ;;
    *)
      [ 0 -ne $verbose ] && echo "ignoring device: $type"
      ;;
  esac
done

# Ugly hack... otherwise keymaps are not always taken into account...
xdotool keyup space

# Keyboard auto-repeat:
# - on and fast
# - enabled for capslock too
xkbset repeatkeys rate 280 14
xkbset repeatkeys 66
xkbset repeatkeys 22

# Enable sticky keys.
xkbset exp 1 \=sticky \=twokey \=latchlock
xkbset sticky -twokey -latchlock

numlockx off

if [ 0 -ne $test_loop ]
then
  xmodmap -pm &&
  xev -event keyboard
fi

