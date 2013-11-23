#! /bin/zsh

XTERM_EXE='xterm'
XTERM_OPTIONS=(+wf)
XTERM_OPTIONS=()
XTERM_EXEC_OPTION='-e'
XTERM_COMMAND=()
XTERM_MPLEX='auto'

SCREEN_EXE=screen
SCREEN_COMMAND=''
SCREEN_RCDIR="${XDG_CONFIG_HOME:-$HOME/.config}/screen/rc.d"
unset STY

TMUX_EXE=tmux
TMUX_COMMAND=''
TMUX_RCDIR="${XDG_CONFIG_HOME:-$HOME/.config}/tmux/rc.d"
unset TMUX TMUX_PANE

DEBUG_CMD=''

test $# -gt 0 -a -z "$1" && shift

if [[ 'auto' == "$XTERM_MPLEX" ]]
then
  XTERM_MPLEX="`which tmux screen | sed -n '/^.*\/\(\w\+\)$/{s//\1/p;q}'`"
fi

while true
do
  case "$1" in
    -h)
      shift
      XTERM_OPTIONS+=-hold
      ;;
    -ssh)
      shift
      XTERM_OPTIONS+=(-title "ssh $1")
      XTERM_COMMAND=(ssh -t "$1")
      shift
      ;;
    -su)
      shift
      XTERM_OPTIONS+=(-title "sudo")
      XTERM_COMMAND=(sudo -i)
      ;;
    -rc)
      shift
      XTERM_OPTIONS+=(-title "$1")
      SCREEN_COMMAND+=(-c "$SCREEN_RCDIR/$1")
      TMUX_COMMAND+=(source-file "$TMUX_RCDIR/$1")
      shift
      ;;
    -nw)
      shift
      XTERM_OPTIONS+=(+wf)
      ;;
    -t)
      shift
      XTERM_OPTIONS+=(-title "$1")
      shift
      ;;
    -d)
      shift
      DEBUG_CMD=1
      ;;
    -a)
      SCREEN_COMMAND=-RR
      TMUX_COMMAND=attach-session
      shift
      ;;
    -m)
      shift
      XTERM_MPLEX="$1"
      shift
      ;;
    -e)
      shift
      break
      ;;
    --)
      break
      ;;
    *)
      break
      ;;
  esac
done

CMD=($XTERM_EXE $XTERM_OPTIONS $XTERM_EXEC_OPTION $XTERM_COMMAND)

case "$XTERM_MPLEX" in
  screen)
    if [ 0 -ne $# ]
    then
      SCREEN_COMMAND=''
    fi
    CMD+=($SCREEN_EXE $SCREEN_COMMAND "$@")
    ;;
  tmux)
    if [ 0 -ne $# ]
    then
      TMUX_COMMAND=new-session
    fi
    CMD+=($TMUX_EXE $TMUX_COMMAND "$*")
    ;;
  *)
    CMD+=("$@")
    ;;
esac

test "$DEBUG_CMD" && set -x
exec $CMD

# vim: shiftwidth=2
