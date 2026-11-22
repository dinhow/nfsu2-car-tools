# NFSU2 car file formats: what we learned

These notes come from reading and rebuilding real NFSU2 (PC) car files. The tools in `tools/` read the stock `GEOMETRY.BIN` and `TEXTURES.BIN` of a car, regenerate them field by field, and write them back **byte-identical**. That is the main proof that the layout below is right.

All values are little-endian. Coordinates are in meters: **X forward, Y left, Z up**.

## Chunks

Every file is a tree of chunks: `u32 id`, `u32 size`, then `size` bytes. An id with the high bit set (`0x80000000`) is a container that holds child chunks. `0x00000000` chunks are padding.

## GEOMETRY.BIN (solid list `0x80134000`)

### Header `0x80134001`

| Chunk | Contents |
|---|---|
| `0x00134002` | Info: object count at `+12`, source path, `"DEFAULT"`. At `+104` the absolute offset and size of the trailing `0x80034020` chunk. Alignment value `0x80`. |
| `0x00134003` | `(hash, 0)` pairs, one per object, sorted by hash. |
| `0x00134004` | 24-byte entries: `hash, absolute offset of the object chunk, total chunk size, size, 0, 0`. Must be rebuilt when objects change size. |

### Objects `0x80134010`

Objects start at **128-byte aligned** offsets; padding chunks are added before them. The child chunks are:

| Chunk | Contents |
|---|---|
| `0x00134011` | 192-byte header (see below). |
| `0x00134012` | Texture hashes, as `(hash, 0)` pairs. |
| `0x00134013` | Shader ("light material") hashes, as `(hash, 0)` pairs. |
| `0x80134100` | Mesh container (see below). |
| `0x0013401A` | Optional markers. |
| `0x00134017/18/19` | Optional data, absent in 108 of the 611 stock Sentra objects. They look like per-position packed normals used to smooth seams between parts. It is safe to drop them for new meshes. |

**Header (`0x00134011`):**

| Offset | Field |
|---|---|
| `+16` | Hash of the full object name (see "Hashes" below) |
| `+20` | Triangle count |
| `+24` | Bytes `[?, number of textures, number of shaders, ?]` |
| `+32` | Bounding box minimum (3 floats) |
| `+48` | Bounding box maximum (3 floats) |
| `+64` | 4×4 matrix; the translation is at `+112` |
| `+148`, `+152` | Area-related floats; copying them from the stock part works |
| `+164` | Name, truncated to 27 characters |

**Mesh container (`0x80134100`):**

| Chunk | Data alignment | Contents |
|---|---|---|
| `0x00134900` | 16 | Description: group count at `+16`, triangle count at `+36`, vertex count at `+52` |
| `0x00134B01` | **128** | Vertices, 36 bytes each: position (3 floats), normal (3 floats), `u32` color, UV (2 floats) |
| `0x00134B02` | 16 | Material groups, 60 bytes each: bbox min (3 floats), index count, bbox max (3 floats), 7 `u32` fields, flags. Field 0 is the texture index, field 1 the shader index, field 6 the start position in the index buffer. |
| `0x00134B03` | 16 | `u16` triangle-list indices. An odd index count gets one extra `0` appended. |

**Padding is `0x11` bytes at the start of a chunk body, until the data reaches the alignment shown above. Compute it from the absolute file position, never from the content:** a vertex can start with the byte `0x11`.

**Markers (`0x0013401A`):** 80-byte records after the `0x11` padding: `u32 name hash`, 12 bytes of padding, then a 4×4 matrix with the position at bytes `+48..+59` of the matrix. Known names include `SPOILER`, `ROOF_SCOOP`, `LEFT_HEADLIGHT`, `RIGHT_HEADLIGHT`, `LEFT_BRAKELIGHT`, `RIGHT_BRAKELIGHT`, `RIGHT_EXHAUST`, `REAR_LICENSE_PLATE`, `FRONT_WINDOW` and `REAR_WINDOW`.

**Local-space parts:** the wheel, brakes, spoiler and exhaust are stored around their own origin. The spoiler uses the header translation (equal to the `SPOILER` marker). In the stock wheel, the spokes sit at low Y (about -0.01 to 0.07) and the inner barrel at high Y.

**Trailing data:** the `0x80034020` chunk after the solid list contains `SENTRA_CV` and `SENTRA_W01_CV`…`W04_CV` records. These are collision outlines: one for the normal body and one per widebody.

### Hashes

`bStringHash`: `h = 0xFFFFFFFF; for each byte c: h = h*33 + c` (32 bits). It is used for object names, texture names and marker names. Object names are truncated in the header, but the full name can be recovered from the hash (for example `SENTRA_KIT00_HEADLIGHT_LEFT_A`).

### Material groups worth knowing (stock Sentra)

| Shader | Use |
|---|---|
| `CARSKIN` | Paint. Texture `0x3C84D757`, flags `0x14180`. The UVs point into the car "skin" render target, which has the stock car's layout; vinyls rely on it. |
| `DULLPLASTIC` | Matte black plastic. |
| `CHROME` | Chrome. |
| `DECAL` | Badges. |
| `HEADLIGHT`, `HEADLIGHTGLASS`, `BRAKELIGHT` | Lights and lenses. These glow at night and when braking. |
| `RUBBER`, `MAGSILVER` | Tyre and rim. |
| `CALIPER` | Brake calipers. |

Window glass uses specific texture and shader pairs found in the `BASE` object. The vertex color depends on the material: paint uses `0xFF000000`, wheels use `0xFFFFFFFF`. Copy it from a stock group with the same texture and shader.

## TEXTURES.BIN (TPK `0xB3300000`)

| Chunk | Contents |
|---|---|
| `0x33310001` | Pack info |
| `0x33310002` | `(hash, 0)` pairs sorted by hash |
| `0x33310003` | 24-byte entries: `hash, absolute offset, compressed size, uncompressed size, 0x100, 0` |
| `0x33320002` | Data. Blobs are aligned to 64 bytes. |

**Compression:** each texture is compressed on its own, with **JDLZ** (EA's LZ codec) or `HUFF`. A JDLZ stream made only of literal bytes is valid, and the game accepts it.

**Uncompressed blob:** pixel data (all mip levels) followed by a 156-byte trailer. The trailer holds the 124-byte TextureInfo and a 32-byte format block (FourCC such as `DXT1`):

| Offset | Field |
|---|---|
| `+12` | Name (24 bytes) |
| `+36` | Hash |
| `+48` | Virtual data offset |
| `+56` | Data size |
| `+68` | Width and height (`u16` each) |
| `+72` | log2 of width and of height |
| `+74` | Compression type: `0x22` = DXT1, `0x24` = DXT3 |
| `+78` | **Mip count** |

## Texture loading behavior (found by testing in game)

1. **Textures appended to a car's TPK do not show up.** Reuse existing entries instead: keep the same hash, size, format and mip count, keep the original trailer, and change only the pixels.
2. **Textures of STYLE parts** (`STYLExx_*`) **only load when that part is equipped.**
3. **The engine texture (`<CAR>_ENGINE`) only loads in the garage, not in races.**
4. Textures of stock exterior parts (`<CAR>_BADGING`, `<CAR>_KIT00_BRAKELIGHT`, `<CAR>_KIT00_HEADLIGHT_*`) are always loaded. They are small (128 px or less), so crop the source texture to the UV region you actually use and remap the UVs.

## CarTypeInfo (wheel positions)

Chunk `0x00034600` in `GLOBAL\GLOBALB.BUN` (and `GlobalB.lzc`) holds 2192-byte records, one per car, starting after 8 bytes of padding. Each record has 4 wheels of 48 bytes, starting at `+288`:

| Offset | Field |
|---|---|
| `+0` | x, y, z |
| `+16` | radius, width, ? |

Stock Sentra values: x = ±1.32 / -1.22, y = ±0.75, hub z = 0.08, radius 0.3172.

## Kits and widebody

- The kit objects are `KIT01`…`KIT29` (bumpers, skirts, hood undersides), `STYLE01`…`STYLE28` (hoods, lights, engines) and `KITW01`…`KITW04` (widebody).
- A widebody `KITWxx_BODY` is a full lower shell: body, both bumpers, skirts and lips. The game uses it instead of the separate bumper and skirt parts.
- `tools/kit_morph.py` fits the stock kits onto a new body shape. It uses an affine bounding-box map plus a smoothed thin-plate-spline residual toward the new stock part's surface.
