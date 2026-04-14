---
name: mdtoc
description: "Add or update a markdown file's table of contents (TOC) based on its header structure. Use when creating new documentation, updating existing files, or ensuring TOC accuracy. Supports GitHub-style TOC with configurable header levels."
argument-hint: "[markdown-file]"
user-invocable: true
---

# Context

This skill generates a table of contents (TOC) for a markdown file by analyzing its header structure. It is designed to be used when creating new documentation, updating existing files, or ensuring that the TOC is accurate and up-to-date. The generated TOC follows GitHub-style formatting and can be configured to include specific header levels.

# Steps

1. **Check for Existing TOC**: Check the target markdown file for existing TOC markers (`<!--TOC-->`).
  1. **Add Base Template**: If no TOC markers are found, insert the base template snippet (listed below) at the top of the markdown file to enable TOC generation (see Examples section below). This includes horizontal rules and `<!--TOC-->` markers where the TOC will be injected.
1. **Update TOC**: Run the `md-toc` tool bash snippet below to analyze the markdown file's header structure and generate a new TOC.

# Base Template Snippet

Add this snippet to the top of the markdown file to enable TOC generation:

```markdown

---

<details>
<summary>Table of Contents</summary>
<!--TOC-->
<!--TOC-->
</details>

---

```

NOTES: 
- The blank lines around the horizontal rules are important for correct TOC placement.
- The `<!--TOC-->` markers denote where the TOC will be injected. Do not remove or alter these markers. The python `md-toc` tool looks for these exact markers to know where to insert the generated TOC.

# `md-toc` Tooling

Run the following command to add or update the TOC in-place:

```sh
uvx --from md-toc md_toc --in-place github --no-list-coherence --header-levels 4 $ARGUMENTS
```

# Examples

**Before** (no TOC):

```markdown
# My Documentation

Overview of the project...

## Installation 

...

## User Guide

...
```

**After** (with TOC base snippet):

```markdown
# My Documentation

Overview of the project...

---

<details>
<summary>Table of Contents</summary>
<!--TOC-->
<!--TOC-->
</details>

---

## Installation 

...

## User Guide

...
```

NOTE:
- The first header and opening text are left as-is and then a TOC goes before the second header.
- If there are existing `<!--TOC-->` markers, then the user has chosen custom placement and we simply update the TOC in-place without adding the base template snippet.

**After** (with TOC updated):

```markdown
# My Documentation

Overview of the project...

---

<details>
<summary>Table of Contents</summary>
<!--TOC-->

1. [My Documentation](#my-documentation)
   1. [Installation](#installation)
   1. [User Guide](#user-guide)

<!--TOC-->
</details>

---

## Installation 

...

## User Guide

...
```

# Troubleshooting

The `md-toc` documents that it has the following exit codes:
> Return values: 0 ok, 1 error, 2 invalid command, 128 TOC differs from the one in the file (see --diff option)

You can self discover the documentation via:

```sh
uvx --from md-toc md_toc --help
```