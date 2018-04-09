#!/bin/zsh

dry_run=0
quality='1080p'
verbose=0
player='youtube-dl'
cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/youtube"

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

player_youtube-dl()
{
  cachedir="${XDG_CACHE_HOME:-$HOME/.cache}/youtube"
  mkdir -p "$cachedir"
  tmpdir="$(mktemp -p "$cachedir" -d -t yt.XXXXXXXXXX)"
  trap "rm -rf ${(Q)tmpdir}" EXIT
  cmd_run youtube-dl --all-subs --embed-subs --add-metadata --merge-output-format=mkv --output="$tmpdir/%(title)s-%(id)s.%(ext)s" --external-downloader aria2c --external-downloader-args "-x 16 -s 16 -k 1M" --quiet -- "$2"
  find "$tmpdir" -maxdepth 1 -type f -name '*.mkv' -print0 |
  xargs -0 --no-run-if-empty mp-play --no-fetch-subtitles --option=--keep-open
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

player_mpv()
{
  if [[ "$1" = "--mp-play" ]]
  then
    mp_play=1
    shift
  else
    mp_play=0
  fi

  quality="$1"
  video="$2"
  cache="$cache_dir/$video"
  cookies="$cache_dir/$video.cookies"
  mpv_opts=(
    --cache-file="$cache"
    --ytdl
    --ytdl-raw-options="cookies=$cookies,format=best"
  )

  if [[ 0 -eq $mp_play ]]
  then
    cmd=(mpv "${(@)mpv_opts}")
  else
    cmd=(mp-play --player=mpv "${(@)mpv_opts/#/--option=}")
  fi
  cmd+=(--profile='youtube' "https://www.youtube.com/watch?v=$video")

  trap '' SIGINT
  cmd_run mkdir -p "$cache_dir"
  cmd_run "${(@)cmd}"
  cmd_run rm -f "$cache" "$cookies"
}

if [[ -x =mpv ]] 2>/dev/null
then
  player_mp-play()
  {
    player_mpv --mp-play "$@"
  }
fi

while [ -n "$1" ]
do
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
    --)
      shift
      break
      ;;
    -*)
      echo 1>&2 "invalid option: $1"
      exit 1
      ;;
    *)
      break
      ;;
  esac
  shift
done

while [ -n "$1" ]
do
  video=''

  case "$1" in
    youtube.com/*)
      # Fallthrough...
      ;&
    https://player.vimeo.com/*)
      video="$1"
      ;;
    http://*)
      # Fallthrough...
      ;&
    https://*)
      # Fallthrough...
      ;&
    youtube://*)
      str="`echo "$1" | sed -n '
        s,#t=\([0-9]\+\)$,,;
        s,^youtube://,,;
        \,^youtube.com/watch?v=\([a-zA-Z0-9_-]\{11\}\)\(?q=\([a-z0-9]\+\)\)\?$,{s,,video='"'"'\1'"'"' quality='"'"'\3'"'"',;s, quality='"''"',,;p;Q0};
        \,^https\?://www.youtube.com/embed/\([a-zA-Z0-9_-]\{11\}\)$,{s,,video='"'"'\1'"'"',p;Q0};
        \,^https\?://youtu\.be/\([a-zA-Z0-9_-]\{11\}\)$,{s,,video='"'"'\1'"'"',p;Q0};
        \,^https\?://.*[?&]\<v=\([a-zA-Z0-9_-]\{11\}\)\(&.*\)\?$,{s,,video='"'"'\1'"'"',p;Q0};
        \,^\([a-zA-Z0-9_-]\{11\}\)\(?q=\([a-z0-9]\+\)\)\?$,{s,,video='"'"'\1'"'"' quality='"'"'\3'"'"',;s, quality='"''"',,;p;Q0};
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
