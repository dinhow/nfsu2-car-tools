# nfsu2-car-tools

**Tools to convert a car model into Need for Speed: Underground 2 (PC)**, rebuilding the game's own `GEOMETRY.BIN` and `TEXTURES.BIN`. No ZModeler needed.

Built while converting the **Nissan Sentra SE-R Spec V B16 (2007–2012)** to replace the stock B15 Sentra. The project is a **work in progress**, and I'm looking for someone who wants to continue it. *Versão em português abaixo.*

| | |
|---|---|
| ![side](docs/screenshots/side_front.png) | ![front](docs/screenshots/front_grille_lights.png) |
| ![rear](docs/screenshots/rear_badges_exhaust.png) | ![rear 3/4](docs/screenshots/rear_three_quarter.png) |

> **No game files, car models or textures are included.** You need your own NFSU2 installation and a source car model you are allowed to use. The tools generate everything locally on your machine.

## What works (tested offline on PC)

- Full B16 body with 3 LODs.
- Paint (color changes), working head and brake lights, fog lights, grille and badges.
- Aftermarket wheels, spoilers, roof scoops and mirrors, with mount points repositioned for the B16.
- 8 B16-based front bumpers: lips, splitters and a blacked-out grille.
- The remaining stock kits, morphed to the B16 shape.
- Wheel positions adjusted for the longer wheelbase (4-value CarTypeInfo patch).

## What's left (help wanted)

- **Vinyl support:** remap the body UVs to the car skin layout. Right now vinyls don't apply.
- **Proper B16 wheels:** the SE-R wheel renders mirrored (see the spoke orientation notes in `docs/FORMAT.md`). For now the stock B15 wheels and brakes are used.
- **STYLE headlights and taillights** still look off.
- **Real bodykits and widebody:** these need proper hand modeling.
- **Collision outlines:** the `CV` records are still the B15 ones.
- **Browser version:** test and adapt for NFSU2 Revived.

## How it works

1. **Extract** the source model (`.kn5`, the Assetto Corsa format) to meshes and textures: `tools/kn5_export.py`.
2. **Build the parts in Blender:** convert the axes, split the model into the game's parts (KIT00 and BASE), decimate it into LODs A, B and C, and compute the mount points: `tools/build_nfsu2.py`.
3. **Dump** the Blender scene for the compiler: `tools/dump_blend.py`.
4. **Textures:** put the new textures into stock texture slots that are always loaded, cropped to the UV region actually used: `tools/build_textures.py`.
5. **Compile** `GEOMETRY.BIN`, using the stock file as a template. This step also:
   - maps every material to a stock texture, shader and flags combination;
   - morphs the stock kits to the new shape;
   - adds the B16 front bumper variants.

   Script: `tools/compile_sentra.py` (`tools/kit_morph.py`, `tools/b16_front.py`).
6. **Patch** the wheel positions in CarTypeInfo: `tools/patch_wheels.py`.
7. **Validate** the result: `tools/validate.py`. You can also check the reader and writer with `tools/roundtrip.py`, which must rewrite the stock file byte-identically.
8. **Install** with a backup: `scripts/install.ps1`. Undo with `scripts/restore.ps1`.

The format details are in **[docs/FORMAT.md](docs/FORMAT.md)**.

### Commands

Requirements: Python 3.10+ with `numpy`, `scipy` and `Pillow`, and Blender 4.x.

```
python tools/kn5_export.py <car.kn5> export/sentra
blender -b -P tools/build_nfsu2.py -- <car.kn5> export/sentra/textures nfsu2_build
blender -b nfsu2_build/sentra_nfsu2.blend -P tools/dump_blend.py -- nfsu2_build/mesh_dump.json
python tools/b16_front.py nfsu2_build/mesh_dump.json nfsu2_build/b16_front.json
python tools/build_textures.py "<game>/CARS/SENTRA/TEXTURES.BIN" export/sentra/textures out_game/CARS/SENTRA/TEXTURES.BIN nfsu2_build/mesh_dump.json
python tools/compile_sentra.py "<game>/CARS/SENTRA/GEOMETRY.BIN" nfsu2_build/mesh_dump.json nfsu2_build/build_report.json nfsu2_build/TEXTURES_new_textures.json out_game/CARS/SENTRA/GEOMETRY.BIN --b16front=nfsu2_build/b16_front.json
python tools/patch_wheels.py "<game>/GLOBAL" out_game/GLOBAL 1.3996 -1.2996
python tools/validate.py "<game>" out_game/CARS/SENTRA/GEOMETRY.BIN out_game/CARS/SENTRA/TEXTURES.BIN "<game>/CARS/SENTRA/GEOMETRY.BIN"
powershell -ExecutionPolicy Bypass -File scripts/install.ps1 -Game "<game>"
```

Always point `GEOMETRY.BIN` and `TEXTURES.BIN` to the **original** files (for example the backup made by `install.ps1`), never to an already modified copy.

Some values in `build_nfsu2.py` and `compile_sentra.py` are specific to the Sentra B16 source model: mesh names, wheel centers and the grille region. To convert another car, adjust those values.

The scripts in `tools/research/` were used to reverse-engineer the formats: chunk walker, part and marker listings, CarTypeInfo dump and render helpers.

Converted with the help of Claude Opus (Anthropic).

---

## Português

**Ferramentas para converter um modelo de carro para o NFSU2 de PC**, reconstruindo o `GEOMETRY.BIN` e o `TEXTURES.BIN` do próprio jogo, sem ZModeler.

Elas foram feitas convertendo o **Nissan Sentra SE-R Spec V B16 (2007–2012)** no lugar do Sentra B15 original. O projeto está **em andamento**, e procuro alguém que queira continuá-lo.

**Nenhum arquivo do jogo, modelo ou textura está incluído.** Você precisa do seu NFSU2 e de um modelo de origem que possa usar. As ferramentas geram tudo localmente.

**O que funciona:**
- Carroceria do B16 com 3 níveis de detalhe.
- Pintura, faróis e lanternas acendendo, faróis de milha, grade e emblemas.
- Rodas aftermarket, aerofólios, entrada de ar no teto e retrovisores.
- 8 para-choques dianteiros baseados no B16.
- Demais kits do jogo adaptados ao formato do B16.
- Posição das rodas ajustada para o entre-eixos maior.

**O que falta:**
- Vinis.
- Rodas próprias do B16, que hoje aparecem espelhadas.
- Faróis e lanternas de estilo.
- Body kits modelados à mão.
- Contornos de colisão.
- Testar na versão de navegador (NFSU2 Revived).

O passo a passo e os comandos estão na seção em inglês acima. Os detalhes do formato estão em [docs/FORMAT.md](docs/FORMAT.md).

Conversão feita com auxílio do Claude Opus (Anthropic).

## License

The code is under the MIT license (see `LICENSE`). Game files, car models and textures belong to their respective owners and are **not** part of this repository.
