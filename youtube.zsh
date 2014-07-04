#!/bin/zsh

dry_run=0
quality='720p'
verbose=0
player='youtube_mpv'

cmd_run()
{
  if [[ 1 -eq $dry_run || 1 -eq $verbose ]]
  then
    echo "$@"
    [[ 1 -eq $dry_run ]] && return
  fi

  "$@"
}

player_smplayer()
{
  case "$1" in
    240p)
      quality='small'
      ;;
    360p)
      quality='medium'
      ;;
    480p)
      quality='large'
      ;;
    720p)
      quality='hd720'
      ;;
    1080p)
      quality='hd1080'
      ;;
  esac
  video="$2"

  cmd_run smplayer -close-at-end "http://youtu.be/$video${quality+?vq=$quality}"
}

player_youtube-viewer()
{
  case "$1" in
    240p)
      quality=2
      ;;
    360p)
      quality=3
      ;;
    480p)
      quality=4
      ;;
    720p)
      quality=7
      ;;
    1080p)
      quality=1
      ;;
  esac
  video="$2"

  cmd_run youtube-viewer -q "-$quality" -id="$video" --std-input=':q'
}

player_youtube_mpv()
{
  quality="$1"
  video="$2"

  cmd_run mp-play --player=mpv --profile='youtube' --option=--quvi-format="$quality" "http://www.youtube.com/watch?v=$video"
}

while [ -n "$1" ]
do
  video=''

  case "$1" in
    -d)
      set -x
      ;;
    -q)
      shift
      quality="$1"
      ;;
    -p)
      shift
      player="$1"
      ;;
    -n)
      dry_run=1
      ;;
    -v)
      verbose=1
      ;;
    -*)
      echo 1>&2 "invalid option: $1"
      exit 1
      ;;
    http://*)
      # Fallthrough...
      ;&
    https://*)
      # Fallthrough...
      ;&
    youtube://*)
      str="`echo "$1" | sed -n '
        \,^https\?://youtu\.be/\([a-zA-Z0-9_-]\{11\}\)$,{s,,video='"'"'\1'"'"',p;Q0};
        \,^https\?://.*?.*\<v=\([a-zA-Z0-9_-]\{11\}\)\(&.*\)\?$,{s,,video='"'"'\1'"'"',p;Q0};
        \,^youtube://\([a-zA-Z0-9_-]\{11\}\)\(?q=\([a-z0-9]\+\)\)\?$,{s,,video='"'"'\1'"'"' quality='"'"'\3'"'"',p;Q0};
        Q1
      '`"
      if [[ $? -ne 0 || -z "$str" ]]
      then
        echo 1>&2 "invalid url: $1"
        exit 1
      fi
      eval "$str"
      ;;
    *)
      video="$1"
      ;;
  esac

  shift

  if [ -n "$video" ]
  then
    case "$quality" in
      240p|360p|480p|720p|1080p)
        ;;
      sd)
        quality='480p'
        ;;
      hd)
        quality='1080p'
        ;;
      *)
        echo 1>&2 "unsupported quality: $quality"
        ;;
    esac

    if [[ 1 -eq $verbose ]]
    then
      echo "video: ${video}"
      echo "quality: ${quality}"
    fi

    "player_$player" "$quality" "$video"
  fi

done
