<!--
Mermaid diagram SOURCE. This file is committed; its render is not.

    make diagrams     # mmdc renders this to build-pipeline-1.png

`mmdc` appends the fence index, so `build-pipeline.md` becomes
`build-pipeline-1.png`. The deck embeds the PNG; the Makefile lists the PNG as a
prerequisite of every render, so editing THIS file rebuilds only this image and
then the deck.

Why a separate file at all: Marp has no Mermaid runtime, so a fenced mermaid
block inside a slide renders as a code listing.

The palette below came from the project's design tokens when this deck was
scaffolded, so the diagram matches the theme without anyone choosing a colour.
Keep it that way: read the values from the theme, do not invent hexes.

Three Mermaid traps worth knowing, each found by rendering, none of which errors:
  * `fontFamily` is a ROOT config key, not a themeVariables entry. Putting it in
    themeVariables silently does nothing and you get a serif fallback.
  * edge labels need `edgeLabelBackground`, or Mermaid tints them from
    `tertiaryColor` and they read as a different colour.
  * the font below is the BARE token (no quotes), and must stay that way. A font
    token is normally written `'Family', fallback` and carries its own quotes,
    which CSS and SVG accept. Mermaid's init parser is not strict JSON: those
    nested quotes end the string early, it discards the WHOLE init, and the
    diagram renders in default colours while reporting success. The scaffold
    supplies a quote-stripped token for exactly this reason.
-->

```mermaid
%%{init: {
  "theme": "base",
  "fontFamily": "{{TOKEN_FONTDISPLAY_BARE}}",
  "themeVariables": {
    "primaryColor": "{{TOKEN_SURFACE}}",
    "primaryTextColor": "{{TOKEN_FG}}",
    "primaryBorderColor": "{{TOKEN_ACCENT}}",
    "lineColor": "{{TOKEN_MUTED}}",
    "tertiaryColor": "{{TOKEN_BG}}",
    "edgeLabelBackground": "{{TOKEN_BG}}",
    "labelColor": "{{TOKEN_FG}}"
  }
}}%%
flowchart LR
  MMD["assets/*.md<br/>mermaid source"] -->|"make diagrams"| PNG["assets/*-1.png<br/>git-ignored"]
  SVG["assets/*.svg<br/>draw.io editable"] --> DECK
  PNG --> DECK["the deck<br/>embeds it"]
  DECK --> OUT["html · pdf · pptx<br/>frames → mp4 → GIF"]
```
