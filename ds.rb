#!/usr/bin/env ruby

SAVE_CURSOR = '7'
RESTORE_CURSOR = '8'
ERASE_CURSOR2EOL = '[2K'

STDOUT.sync = true

lines = []

rd, wr = IO.pipe

pid = fork {

  rd.close
  STDOUT.reopen(wr)

  cmd = ['du', '-xh', '--exclude=./.?*', '--max-depth=1']
  cmd << '-c' if ARGV.size > 1
  cmd.concat(ARGV)
  exec(*cmd)
  exit 255
}

wr.close

DU_BLOCK_SIZES = {
  ''  => 1,
  'K' => 1024,
  'M' => 1024*1024,
  'G' => 1024*1024*1024,
  'T' => 1024*1024*1024*1024,
}

DUEntry = Struct.new(:path, :size, :block_size)

class DUEntry

  def real_size

    size * DU_BLOCK_SIZES[block_size]

  end

  def <=>(e)

    self.real_size <=> e.real_size

  end

  def to_s(align = 0)

    '%*u%s %s' % [ align, size, block_size, path ]

  end

end

print SAVE_CURSOR if STDOUT.tty?

align = 0

while line = rd.gets

  line.chomp!

  unless line =~ /^(\d+(\.\d+)?)([KMGT])?\s+(.*)$/
    STDERR.puts "line doesn't match: #{line}"
    next
  end

  line = DUEntry.new($4, $1.to_f, $3 ? $3 : '')

  lines << line

  if line.size > 0
    line_align = Math.log10(line.size).ceil
    align = line_align if line_align > align
  end

  print RESTORE_CURSOR, ERASE_CURSOR2EOL, line.to_s(align) if STDOUT.tty?

end

print RESTORE_CURSOR, ERASE_CURSOR2EOL if STDOUT.tty?

lines.sort!
lines.each { |l| puts l.to_s(align) }

