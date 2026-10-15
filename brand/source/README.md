# Brand asset generator

`build.py` regenerates every file in `brand/` (SVG, PNG, ICO, social images, tokens, brand sheet) from `lib.py`.

Needs: Python 3, `pip install cairosvg pillow fonttools`, and the three open-licensed fonts in `brand/source/fonts/`
(or set `DEVMIND_FONTS_DIR`): `IBMPlexSans-SemiBold.ttf`, `IBMPlexSans-Medium.ttf`, `IBMPlexSans-Regular.ttf`,
`JetBrainsMono[wght].ttf`, `InstrumentSerif-Regular.ttf` (all SIL Open Font License; confirm before redistributing).

Run: `python3 brand/source/build.py`. Do not edit generated files by hand; edit `lib.py` or `build.py`.
