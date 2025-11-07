---
description: "Update Mermaid.JS diagrams"
---

# Context

Setup and maintain automatic project diagrams using Mermaid.JS

# Workflow

- If folder `docs/diagrams/` does not exist then create it.
- If `docs/diagrams/Makefile` does not exist then create it with this exact content:
  ```Makefile
    # When a MermaidJS source file (*.mmd) is updated, generate a corresponding PNG file.
    %.png: %.mmd
        npx -p @mermaid-js/mermaid-cli mmdc --input $< --output $@ --theme default --backgroundColor white --scale 4

    # A top level target to mark that all diagrams have a correpsonding png that should exist if it doesn't already.
    diagrams: $(patsubst %.mmd,%.png,$(wildcard *.mmd))
  ```
    - Check the commands in the Makefile target are indented with tabs and not spaces.
- For each `docs/diagrams/*.mmd` files
    - analyse the codebase to create an updated version of the .mmd file so it reflects an accurate and up to date lens view of the code base this diagrams is portraying.
- Run `make -C docs/diagrams diagrams` to refresh the updated versions of the diagrams generated as PNGs.
- If the README.md has a section with these diagrams already in it, 
    - ensure all diagrams are documented in that same section of the README.md. 
    - Each of the PNG images should use a markdown image tag to actually render the image in the README.
    - Under each image there should be a markdown link referencing the source file.
