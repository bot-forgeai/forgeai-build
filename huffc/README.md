# huffc

A small Huffman-coding file compressor — no third-party dependency,
just `heapq` and hand-rolled bit packing.

## Quick start

```
pip install -e .
huffc compress input.txt input.huf
huffc decompress input.huf roundtrip.txt
huffc stats input.txt
```

Or `python -m huffc ...` if you don't want to install the console
script.

## How it works

- `huffc/huffman.py` builds a canonical Huffman tree from a byte
  frequency table (`heapq`-based, ties broken by symbol value so the
  compressor and decompressor always agree on tree shape regardless
  of dict iteration order) and assigns each byte a variable-length
  bit code.
- `huffc/bitio.py` packs/unpacks those bit codes into a byte stream,
  zero-padding the final partial byte.
- `huffc/format.py` defines the on-disk container: a `HUFC1` magic
  number, the frequency table (so the decoder can rebuild the exact
  same tree), then the packed bitstream. The frequency table's total
  also tells the decoder exactly how many symbols to decode, so no
  separate padding-length field is needed.

## CLI

- `huffc compress INPUT OUTPUT [-q/--quiet]` — compress a file,
  printing the size reduction unless `-q` is given.
- `huffc decompress INPUT OUTPUT [-q/--quiet]` — decompress a file
  produced by `compress`; exits 1 with a clean error message on a
  file that isn't a valid huffc container.
- `huffc stats INPUT` — report original/compressed size and ratio
  without writing an output file.

Any of these accept `-` for `INPUT` or `OUTPUT` to read from stdin or
write to stdout, so huffc composes in a shell pipeline:

```
cat input.txt | huffc compress - - > input.huf
huffc decompress - - < input.huf | diff - input.txt
```

The human-readable summary line is suppressed whenever the output
side is `-`, since it would otherwise corrupt the piped binary
stream.

## Multi-file archives

- `huffc archive OUTPUT INPUT... [-q/--quiet]` — compress several
  files into one `.hfa` archive, each entry independently
  Huffman-compressed via the same `format.compress` used for a single
  file (`huffc/archive.py` just adds a name+length-prefixed container
  around per-file blobs, so all the Huffman logic stays in one place).
  Entry names are always just each input path's basename — directory
  components are stripped, so extracting can never write outside the
  target directory (and two inputs with the same basename in
  different directories will collide).
- `huffc list ARCHIVE` — print each entry's name and decompressed
  size without extracting.
- `huffc extract ARCHIVE [-o/--outdir DIR] [-q/--quiet]` — decompress
  every entry into `DIR` (default: current directory), recreating any
  relative subdirectories in the stored names; exits 1 with a clean
  error message on a file that isn't a valid huffc archive.

## Compression ratio

huffc gets its best ratios on data with skewed byte frequencies
(natural-language text, anything with a lot of repetition). On
already-dense or random binary data, the container's own overhead
(magic bytes plus a per-distinct-byte frequency table entry) can
make the "compressed" output slightly larger than the input — this
is inherent to Huffman coding, not a bug.
