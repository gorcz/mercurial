# parsers.py - Python implementation of parsers.c
#
# Copyright 2009 Matt Mackall <mpm@selenic.com> and others
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from mercurial.node import nullid
import struct, zlib, cStringIO

_pack = struct.pack
_unpack = struct.unpack
_compress = zlib.compress
_decompress = zlib.decompress

# Some code below makes tuples directly because it's more convenient. However,
# code outside this module should always use dirstatetuple.
def dirstatetuple(*x):
    # x is a tuple
    return x

def parse_index2(data, inline):
    def gettype(q):
        return int(q & 0xFFFF)

    def offset_type(offset, type):
        return long(long(offset) << 16 | type)

    indexformatng = ">Qiiiiii20s12x"

    s = struct.calcsize(indexformatng)
    index = []
    cache = None
    off = 0

    l = len(data) - s
    append = index.append
    if inline:
        cache = (0, data)
        while off <= l:
            e = _unpack(indexformatng, data[off:off + s])
            append(e)
            if e[1] < 0:
                break
            off += e[1] + s
    else:
        while off <= l:
            e = _unpack(indexformatng, data[off:off + s])
            append(e)
            off += s

    if off != len(data):
        raise ValueError('corrupt index file')

    if index:
        e = list(index[0])
        type = gettype(e[0])
        e[0] = offset_type(0, type)
        index[0] = tuple(e)

    # add the magic null revision at -1
    index.append((0, 0, 0, -1, -1, -1, -1, nullid))

    return index, cache

def parse_dirstate(dmap, copymap, st):
    parents = [st[:20], st[20: 40]]
    # dereference fields so they will be local in loop
    format = ">cllll"
    e_size = struct.calcsize(format)
    pos1 = 40
    l = len(st)

    # the inner loop
    while pos1 < l:
        pos2 = pos1 + e_size
        e = _unpack(">cllll", st[pos1:pos2]) # a literal here is faster
        pos1 = pos2 + e[4]
        f = st[pos2:pos1]
        if '\0' in f:
            f, c = f.split('\0')
            copymap[f] = c
        dmap[f] = e[:4]
    return parents

def pack_dirstate(dmap, copymap, pl, now):
    now = int(now)
    cs = cStringIO.StringIO()
    write = cs.write
    write("".join(pl))
    for f, e in dmap.iteritems():
        if e[0] == 'n' and e[3] == now:
            # The file was last modified "simultaneously" with the current
            # write to dirstate (i.e. within the same second for file-
            # systems with a granularity of 1 sec). This commonly happens
            # for at least a couple of files on 'update'.
            # The user could change the file without changing its size
            # within the same second. Invalidate the file's mtime in
            # dirstate, forcing future 'status' calls to compare the
            # contents of the file if the size is the same. This prevents
            # mistakenly treating such files as clean.
            e = dirstatetuple(e[0], e[1], e[2], -1)
            dmap[f] = e

        if f in copymap:
            f = "%s\0%s" % (f, copymap[f])
        e = _pack(">cllll", e[0], e[1], e[2], e[3], len(f))
        write(e)
        write(f)
    return cs.getvalue()
