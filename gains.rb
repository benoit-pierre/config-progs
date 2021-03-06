#!/usr/bin/env ruby
#
# Copyright (C) 2007  <benoit.pierre@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#

require 'find'

module Gain

  MAPPING = {
    'flac' => 'flac',
    'mp3' => 'mp3',
    'ogg' => 'vorbis',
  }

  def self.has_mp3gain?(*files)

    files.each do |file|

      has_gain = false

      rd, wr = IO.pipe

      if fork

        wr.close

        while rd.gets

          next unless $_ =~ /^(.*)(\t-?[0-9.]+){10}$/

          has_gain = true

        end

        Process.wait

      else

        rd.close
        STDOUT.reopen(wr)

        exec('mp3gain', '-o', '-s', 'c', *files)

      end

      return false unless has_gain

    end

    true

  end

  def self.mp3gain(*files)

    system('mp3gain', '-s', 'r', '-a', '-k', *files)

  end

  def self.has_vorbisgain?(*files)

    files.each do |file|

      has_gain = false

      rd, wr = IO.pipe

      if fork

        wr.close

        until rd.eof

          next unless rd.gets =~ /^REPLAYGAIN_ALBUM_GAIN=.*$/i

          has_gain = true

        end

        Process.wait

      else

        rd.close
        STDOUT.reopen(wr)

        exec('vorbiscomment', '-l', file)

      end

      return false unless has_gain

    end

    true

  end

  def self.vorbisgain(*files)
    system('vorbisgain', '-a', '-f', *files)
  end

  def self.has_flacgain?(*files)

    files.each do |file|

      has_gain = false

      rd, wr = IO.pipe

      if fork

        wr.close

        until rd.eof

          next unless rd.gets =~ /^\s+comment\[\d+\]: REPLAYGAIN_ALBUM_GAIN=.*$/

          has_gain = true

        end

        Process.wait

      else

        rd.close
        STDOUT.reopen(wr)

        exec('metaflac', '--list', '--block-type=VORBIS_COMMENT', file)

      end

      return false unless has_gain

    end

    true

  end

  def self.flacgain(*files)

    system('metaflac', '--add-replay-gain', *files)

  end

end

def gains(dir, dry_run, force, *files)

  f = files[0]

  raise "unsupported file type #{f}" unless f =~ /\.(\w+)$/i

  ext = $1.downcase
  type = Gain::MAPPING[ext]

  raise "unsupported file type #{f}" unless type

  cwd = Dir.pwd
  Dir.chdir(dir)

  if not force and Gain.method("has_#{type}gain?").call(*files)
    puts "skip #{dir} [#{type}]"
  else
    puts "gains #{dir} [#{type}]"
    Gain.method("#{type}gain").call(*files) unless dry_run
  end

  Dir.chdir(cwd)

end

dry_run = false
force = false

puts ARGV if $DEBUG

if '-n' == ARGV[0]
  dry_run = true
  ARGV.shift
end

if '-f' == ARGV[0]
  force = true
  ARGV.shift
end

groups = {}

ARGV.each { |dir|

  next unless File.directory?(dir)

  Find.find(dir) { |path|

    next unless File.file?(path)

    next unless path =~ /\.(mp3|ogg|flac)$/i

    dir, file = File.split(path)

    ((groups[dir] ||= {})[$1] ||= []) << file
  }
}

puts groups if $DEBUG

groups = groups.to_a
groups.sort!
groups.each do |dir, files|

  files.values.each do |files|

    files.sort!

    gains(dir, dry_run, force, *files)

  end
end

# vim: sw=2
