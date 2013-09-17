#! /bin/zsh

dry_run=0
quality='720p'
verbose=0
player='youtube_mpv'

cmd_run()
{
  if [[ 1 -eq $dry_run || 1 -eq $verbose ]]
  then
    echo "$@"
    [[ 1 -eq $dry_run ]] && exit
  fi

  "$@"
}

player_smplayer()
{
  case "$1" in
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

player_youtube_viewer()
{
  case "$1" in
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

  cmd_run youtube-viewer --mplayer='mp-play' --append-mplayer='--player=mplayer --' "-$quality" -I -q -id="$video"
}

player_youtube_mpv()
{
  quality="$1"
  video="$2"
  url="http://www.youtube.com/watch?v=$video"
  typeset -A formats

  for format in `quvi --verbosity=quiet --query-formats "$url" | sed -n '/^\(\(fmt[0-9]\+_[^-| ]\+|\?\)\+\) : .*$/{s//\1/;s/|/ /gp}'`
  do
    case "$format" in
      fmt102_720p)
        # WebM 720p VP8 3D.
        continue
        ;;
      fmt84_720p)
        # MP4 720p H.264 3D.
        continue
        ;;
      *_480p)
        ;;
      *_720p)
        ;;
      *_1080p)
        ;;
      *)
        continue
        ;;
    esac
    formats[$format]="$format"
  done

  [[ 1 -eq $verbose ]] && echo "formats: ${formats[@]}"

  format=''
  while [[ -z "$format" ]]
  do
    case "$quality" in
      480p)
        # fmt35_480p: 480p FLV
        # fmt44_480p: 480p WebM
        format="${formats[fmt44_480p]:-${formats[fmt35_480p]}}"
        [[ -z "$format" ]] && format='default' # Use default format...
        ;;
      720p)
        # fmt22_720p: 720p MP4
        # fmt45_720p: 720p WebM
        format="${formats[fmt45_720p]:-${formats[fmt22_720p]}}"
        [[ -z "$format" ]] && quality='480p' # Try a lower quality.
        ;;
      1080p)
        # fmt37_1080p: 1080p MP4
        # fmt46_1080p: 1080p WebM
        format="${formats[fmt46_1080p]:-${formats[fmt37_1080p]}}"
        [[ -z "$format" ]] && quality='720p' # Try a lower quality.
        ;;
    esac
  done

  cmd_run mp-play --player=mpv --profile='youtube' --option=--quvi-format="$format" "http://www.youtube.com/watch?v=$video"
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
    youtube://*)
      str="`echo "$1" | sed -n "s,^youtube://\([a-zA-Z0-9_-]\{11\}\)\(?q=\([a-z0-9]\+\)\)\?$,video='\1' quality='\3',p"`"
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
      480p|720p|1080p)
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
