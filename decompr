#! /usr/bin/env ruby
#
# Copyright (C) 2008 Benoit Pierre <benoit.pierre@gmail.com>
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

begin

  require 'mahoro'

  mahoro = Mahoro.new(Mahoro::MIME)
  mahoro.extend(Module.new do

    ARCHIVE_TYPES = {
      'application/x-7z-compressed' => '7z',
      'application/x-bzip2' => 'tbz2',
      'application/x-gzip' => 'tgz',
      'application/x-lha' => 'lzh',
      'application/x-rar' => 'rar',
      'application/x-xz' => 'tbxz',
      'application/zip' => 'zip',
    }

    def guess_archive_type(file)

      ARCHIVE_TYPES.fetch(self.file(file), nil)

    end

  end)

rescue LoadError

  mahoro = nil

end

Archiver = Struct.new(:name , :cmd, :dir, :extract, :keep, :list, :overwrite, :pipe, :quiet , :test, :verbose, :extensions)

ace = Archiver.new(   'ace' , nil , nil , '-x'    , nil  , '-t' , '-o+'     , '-p' , nil    , 't'  , '-v'    , ['ace'])
lha = Archiver.new(   'lha' , nil , nil , '-x'    , nil  , '-l' , 'f'       , '-p' , nil    , 't'  , 'v'     , ['lzh'])
rar = Archiver.new(   'rar' , nil , nil , 'x'     , '-o-', 'lt' , '-o+'     , 'p'  , nil    , 't'  , '-v'    , ['rar', 'cbr'])
svz = Archiver.new(   '7z'  , nil , nil , 'x'     , nil  , 'l'  , nil       , '-so', '-bd'  , 't'  , nil     , ['7z'])
tar = Archiver.new(   'tar' , nil , nil , '-x'    , '-k' , '-t' , nil       , '-O' , nil    , '-t' , '-v'    , ['tar'])
zip = Archiver.new(   'zip' , nil , nil , '-x'    , '-n' , '-l' , '-o'      , '-p' , nil    , '-t' , nil     , ['zip', 'cbz', 'jar', 'pk3'])

[tar, tgz = tar.dup, tbz = tar.dup, tbxz = tar.dup].each\
{
  |a|

  a.cmd = ['tar']

  def a.command(options, file)
    [cmd, options, '-f', file]
  end
}

tgz.name = 'tgz'
tgz.cmd << '--gzip'
tgz.extensions = ['tar.gz', 'tar.z', 'tgz']

tbz.name = 'tbz'
tbz.cmd << '--bzip2'
tbz.extensions = ['tar.bz2', 'tbz2', 'tbz']

tbxz.name = 'tbxz'
tbxz.cmd << '--xz'
tbxz.extensions = ['tar.xz']

svz.cmd = '7z'

zip.cmd = 'unzip'

lha.cmd = 'lha'

def lha.command(options, file)
  options.sort!
  [cmd, options.join(''), file]
end

option =
{
  '--directory' => :dir       ,
  '--extract'   => :extract   ,
  '--keep'      => :keep      ,
  '--list'      => :list      ,
  '--overwrite' => :overwrite ,
  '--pipe'      => :pipe      ,
  '--quiet'     => :quiet     ,
  '--test'      => :test      ,
  '--verbose'   => :verbose   ,
  '-d'          => :dir       ,
  '-e'          => :extract   ,
  '-k'          => :keep      ,
  '-l'          => :list      ,
  '-o'          => :overwrite ,
  '-p'          => :pipe      ,
  '-q'          => :quiet     ,
  '-t'          => :test      ,
  '-v'          => :verbose   ,
}

class Archiver

  def command(options, file)
    [cmd, options, file]
  end

end

archivers = {}
extensions = {}

ObjectSpace.each_object(Archiver)\
{
  |a|

   a.cmd ||= a.name.to_s
   archivers[a.name] = a
   a.extensions.each { |ext| extensions[ext] = a }
}

exclude =
{
  :extract   => [ :test, :pipe, :list    ],
  :keep      => [ :overwrite             ],
  :list      => [ :extract, :test, :pipe ],
  :overwrite => [ :keep                  ],
  :pipe      => [ :extract, :test, :list ],
  :quiet     => [ :verbose               ],
  :test      => [ :extract, :pipe, :list ],
  :verbose   => [ :quiet                 ],
}

before =
{
  :dir => proc\
  {
    |dir, archive|

    dir = dir.dup
    dir.gsub!(/%b/, File.basename(archive).sub(/\.\w+$/, ''))
    if File.exist?(dir)
      raise "`#{dir}' already exists and is not a directory" unless FileTest.directory?(dir)
    else
      Dir.mkdir(dir)
    end
    Dir.chdir(dir)
    nil
  }
}

default_options = [ option['-e'], option['-v'] ]

options = default_options.dup

code = 0
args = ARGV.dup
cwd = File.expand_path(Dir.pwd)

while args.size > 0

  Dir.chdir(cwd)

  arg = args.shift

  if arg =~ /^-/

    if arg =~ /^-[A-Z]$/
      global = true
      arg = arg.downcase
    else
      global = false
    end

    unless opt = option[arg]
      raise "invalid option: `#{arg}'"
    end

    ex = exclude[opt]
    ex.each\
    {
      |ex|

      options.delete(ex)
      default_options.delete(ex) if global
    } if ex

    options << opt
    default_options << opt if global
    if pre = before[opt]
      arg = [pre, args.shift]
      options << arg
      default_options << arg if global
    end

  else

    ext = nil

    ext = mahoro.guess_archive_type(arg) if mahoro

    unless ext

      arg =~ /\.((tar\.)?[^.]+)$/

        unless $1
          raise "unknown file format `#{arg}'"
          next
        end

      ext = $1.downcase

    end

    archiver = extensions.fetch(ext)

    archive = File.expand_path(arg)

    options.collect!\
    {
      |opt|

      case opt
      when Array
        opt[0].call(opt[1], archive)
      else
        archiver[opt]
      end
    }
    options.compact!

    cmd = archiver.command(options, archive)
    cmd.flatten!
    cmd.compact!

    puts cmd.join(' ') if $DEBUG

    system(*cmd)

    code |= $?

    options = default_options.dup

  end

end

exit code

# vim: shiftwidth=2
