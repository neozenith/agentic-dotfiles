#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0",
# ]
# ///
"""
curate.py — split/trim a source video into chapter mp4s per a hand-edited JSON
spec. Pure: the source video is never modified; chapter outputs are overwritten
on each run.

Python port of curate.mjs. Feature parity is verified by running both with
--probe and --dry-run against the same config and diffing the output. See the
Workflow section in SKILL.md for project layout and config schema.

Config (default: ./edits.json relative to cwd, override with --config <path>):
    {
      "project":       "myproject",                                // optional
      "naming":        "{project}-Ch{n}-{title}-{dur}.mp4",        // optional, default "Ch{n}-{title}-{dur}.mp4"
      "source":        "originals/source.mp4",                     // optional, auto-detected from originals_dir
      "originals_dir": "originals",                                 // optional, default "originals"
      "output_dir":    "curated",                                   // optional, default "curated"
      "chapters": [
        {
          "name": "introduction",
          "start_ts": "00:01:00",
          "end_ts":   "00:05:55",
          "cuts": [
            { "start_ts": "00:03:00", "end_ts": "00:03:10", "notes": "filler" }
          ],
          "notes": "optional chapter notes"
        }
      ]
    }

Naming-template tokens: {project} {n} {title} {dur} {start} {end}

Usage:
    curate.py                          # process every chapter in ./edits.json
    curate.py --config path/edits.json
    curate.py --only Ch07,intro        # filter by Ch## tag, title slug, or full filename
    curate.py --dry-run                # print the ffmpeg plan, don't execute
    curate.py --probe                  # print keep-segments per chapter, don't encode
    curate.py --input <file.mp4>       # override source video
    curate.py --no-yaml                # skip writing the derived edits.yaml

Requires: ffmpeg + ffprobe in PATH.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

DEFAULT_NAMING = "Ch{n}-{title}-{dur}.mp4"
DEFAULT_ORIGINALS_DIR = "originals"
DEFAULT_OUTPUT_DIR    = "curated"

# ---------- timestamp helpers ----------

def ts_to_sec(ts: str | float | int) -> float:
    if isinstance(ts, (int, float)):
        return float(ts)
    s = str(ts).strip()
    if not s:
        raise ValueError("Empty timestamp")
    if s.replace(".", "", 1).isdigit():
        return float(s)
    parts = [p.strip() for p in s.split(":")]
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    raise ValueError(f"Unrecognised timestamp: {ts}")

def sec_to_ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    # 3-digit ms, total seconds field width 6 (e.g. "05.000" or "59.999")
    return f"{h:02d}:{m:02d}:{s:06.3f}"

def sec_to_dur_tag(t: float) -> str:
    total = max(0, round(t))
    m = total // 60
    s = total % 60
    return f"{m:02d}m{s:02d}s"

# ---------- naming template ----------

def render_filename(template: str, ctx: dict[str, str]) -> str:
    import re
    def sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in ctx:
            valid = ", ".join(ctx.keys())
            raise ValueError(f'Unknown naming token "{{{key}}}". Valid tokens: {valid}')
        return ctx[key]
    return re.sub(r"\{(\w+)\}", sub, template)

def chapter_filename(template: str, project: str | None, index: int, title: str,
                     start_sec: float, end_sec: float, final_sec: float) -> str:
    ctx = {
        "project": project or "",
        "n":       f"{index + 1:02d}",
        "title":   title,
        "dur":     sec_to_dur_tag(final_sec),
        "start":   sec_to_dur_tag(start_sec),
        "end":     sec_to_dur_tag(end_sec),
    }
    return render_filename(template, ctx)

# ---------- chapter math ----------

def compute_chapter_math(start_sec: float, end_sec: float, cuts_input: list[dict],
                         warnings: list[str], chapter_name: str = "") -> dict:
    if end_sec <= start_sec:
        raise ValueError(f"Chapter end ({end_sec}) must be > start ({start_sec})")

    clean = []
    for idx, c in enumerate(cuts_input or []):
        s0 = ts_to_sec(c["start_ts"])
        e0 = ts_to_sec(c["end_ts"])
        s = max(s0, start_sec)
        e = min(e0, end_sec)
        if s0 < start_sec or e0 > end_sec:
            warnings.append(
                f'chapter "{chapter_name}" cut #{idx + 1} '
                f'({c["start_ts"]}–{c["end_ts"]}) extends past the chapter window and was clamped'
            )
        if e > s:
            clean.append({"s": s, "e": e, "raw": c, "orig_idx": idx})
    clean.sort(key=lambda x: x["s"])

    merged: list[dict] = []
    for c in clean:
        prev = merged[-1] if merged else None
        if prev and c["s"] <= prev["e"]:
            warnings.append(
                f'chapter "{chapter_name}" has overlapping cuts '
                f'({prev["raw"]["start_ts"]}–{prev["raw"]["end_ts"]}) '
                f'and ({c["raw"]["start_ts"]}–{c["raw"]["end_ts"]}); merged'
            )
            prev["e"] = max(prev["e"], c["e"])
            prev["notes"] = " / ".join(
                n for n in [prev["raw"].get("notes"), c["raw"].get("notes")] if n
            ) or None
            prev["merged"] = True
        else:
            merged.append({
                "s": c["s"], "e": c["e"], "raw": c["raw"],
                "notes": c["raw"].get("notes"), "merged": False,
            })

    # Walk the window, emitting keep ranges between cuts.
    keep: list[dict] = []
    cursor = start_sec
    for c in merged:
        if c["s"] > cursor:
            keep.append({"s": cursor, "e": c["s"]})
        cursor = max(cursor, c["e"])
    if cursor < end_sec:
        keep.append({"s": cursor, "e": end_sec})

    original_dur_for_pct = end_sec - start_sec
    PREVIEW_PAD = 5
    output_cursor = 0.0
    enriched_cuts = []
    for i, c in enumerate(merged):
        keep_seg = keep[i] if i < len(keep) else None
        if keep_seg is not None:
            output_cursor += keep_seg["e"] - keep_seg["s"]
        cut_dur = c["e"] - c["s"]
        preview_sec = max(start_sec, c["s"] - PREVIEW_PAD)
        enriched_cuts.append({
            "start_ts":              c["raw"]["start_ts"],
            "end_ts":                c["raw"]["end_ts"],
            "cut_duration":          sec_to_ts(cut_dur),
            "cut_pct_of_chapter":    f"{cut_dur / original_dur_for_pct * 100:.1f}%",
            "relative_cut_start_ts": sec_to_ts(c["s"] - start_sec),
            "relative_cut_end_ts":   sec_to_ts(c["e"] - start_sec),
            "output_join_ts":        sec_to_ts(output_cursor),
            "preview_seek_ts":       sec_to_ts(preview_sec),
            "notes":                 c["notes"],
        })

    total_cut = sum(c["e"] - c["s"] for c in merged)
    original_dur = end_sec - start_sec
    return {
        "keep": keep,
        "enriched_cuts": enriched_cuts,
        "original_dur": original_dur,
        "total_cut": total_cut,
        "final_dur": original_dur - total_cut,
    }

def compute_keep_segments(start_sec: float, end_sec: float, cuts: list[dict]) -> list[dict]:
    return compute_chapter_math(start_sec, end_sec, cuts, [])["keep"]

# ---------- derived doc / YAML ----------

YAML_HEADER = """\
# Derived from edits.json — DO NOT EDIT BY HAND.
# Regenerated every time curate runs; edit edits.json then re-run.
#
# Field guide:
#   original_duration       length of the chapter window in the source video
#   total_cut_duration      sum of all cut durations for this chapter
#   cut_pct                 percentage of the chapter that is cut
#   final_duration          length of the curated mp4 (original - cuts)
#   cut_count               number of cuts in the chapter
#   relative_cut_start_ts   where the cut starts WITHIN the chapter window
#   cut_pct_of_chapter      this cut as a % of the chapter (gauge edit aggressiveness)
#   output_join_ts          where the splice lands in the curated mp4 — seek here to verify the join
#   preview_seek_ts         absolute source ts to seek to for a run-up before each cut

"""

def build_derived_doc(config: dict, input_path: Path, project_dir: Path,
                      output_dir: str, chapters: list[dict], naming_template: str) -> dict:
    all_warnings: list[str] = []
    yaml_chapters = []

    # Cross-chapter coverage warnings (gaps / overlaps between consecutive chapters
    # in declared order — not sorted, since edits.json order is the source of truth).
    for i in range(1, len(chapters)):
        prev = chapters[i - 1]
        curr = chapters[i]
        if not prev.get("end_ts") or not curr.get("start_ts"):
            continue
        gap = ts_to_sec(curr["start_ts"]) - ts_to_sec(prev["end_ts"])
        if gap > 0.001:
            all_warnings.append(
                f'gap of {sec_to_ts(gap)} between "{prev["name"]}" (ends {prev["end_ts"]}) '
                f'and "{curr["name"]}" (starts {curr["start_ts"]})'
            )
        elif gap < -0.001:
            all_warnings.append(
                f'overlap of {sec_to_ts(-gap)} between "{prev["name"]}" (ends {prev["end_ts"]}) '
                f'and "{curr["name"]}" (starts {curr["start_ts"]})'
            )

    total_orig = total_cut = total_final = 0.0
    chapters_with_cuts = 0
    for idx, ch in enumerate(chapters):
        s_sec = ts_to_sec(ch["start_ts"])
        e_sec = ts_to_sec(ch["end_ts"])
        math = compute_chapter_math(s_sec, e_sec, ch.get("cuts") or [], all_warnings, ch["name"])
        total_orig  += math["original_dur"]
        total_cut   += math["total_cut"]
        total_final += math["final_dur"]
        if math["enriched_cuts"]:
            chapters_with_cuts += 1

        out_name = chapter_filename(
            naming_template, config.get("project"), idx, ch["name"],
            s_sec, e_sec, math["final_dur"],
        )
        yaml_chapters.append({
            "name":               ch["name"],
            "start_ts":           ch["start_ts"],
            "end_ts":             ch["end_ts"],
            "original_duration":  sec_to_ts(math["original_dur"]),
            "total_cut_duration": sec_to_ts(math["total_cut"]),
            "cut_pct":            f"{math['total_cut'] / math['original_dur'] * 100:.1f}%",
            "final_duration":     sec_to_ts(math["final_dur"]),
            "has_cuts":           len(math["enriched_cuts"]) > 0,
            "cut_count":          len(math["enriched_cuts"]),
            "output_file":        f"{output_dir}/{out_name}",
            "cuts":               math["enriched_cuts"],
            "notes":              ch.get("notes"),
        })

    return {
        "project":      config.get("project"),
        "naming":       naming_template,
        "source":       str(input_path.relative_to(project_dir)) if input_path.is_relative_to(project_dir) else str(input_path),
        "output_dir":   output_dir,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "totals": {
            "chapters":                len(chapters),
            "chapters_with_cuts":      chapters_with_cuts,
            "total_original_duration": sec_to_ts(total_orig),
            "total_cut_duration":      sec_to_ts(total_cut),
            "total_final_duration":    sec_to_ts(total_final),
        },
        "warnings": all_warnings,
        "chapters": yaml_chapters,
    }

def emit_yaml(doc: dict) -> str:
    # Strip None-valued keys so PyYAML doesn't emit "notes: null" everywhere.
    def prune(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: prune(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [prune(x) for x in obj]
        return obj
    body = yaml.safe_dump(prune(doc), sort_keys=False, allow_unicode=True, default_flow_style=False)
    return YAML_HEADER + body

# ---------- source video discovery ----------

def find_input(config: dict, project_dir: Path, cli_input: str | None) -> Path:
    explicit = cli_input or config.get("source")
    if explicit:
        p = Path(explicit)
        return p if p.is_absolute() else (project_dir / p).resolve()
    orig_dir = project_dir / (config.get("originals_dir") or DEFAULT_ORIGINALS_DIR)
    mp4s = sorted(
        f for f in orig_dir.iterdir()
        if f.suffix.lower() == ".mp4" and not f.name.lower().endswith("--subbed.mp4")
    )
    if not mp4s:
        raise FileNotFoundError(f'No .mp4 found in {orig_dir} (and no "source" set in config)')
    if len(mp4s) > 1:
        raise RuntimeError(
            f'Multiple .mp4s in {orig_dir}; set "source" in config or pass --input to disambiguate.'
        )
    return mp4s[0]

# ---------- chapter filtering ----------

def should_process(name: str, index: int, out_filename: str, only: list[str]) -> bool:
    if not only:
        return True
    ch_tag = f"Ch{index + 1:02d}"
    candidates = [name, ch_tag, out_filename, out_filename.removesuffix(".mp4")]
    return any(
        c == needle or c.startswith(needle + "-") or c.startswith(needle)
        for needle in only
        for c in candidates
    )

# ---------- ffmpeg ----------

def build_filter_complex(keep: list[dict], seek_offset: float = 0.0) -> str:
    parts = []
    labels = []
    for i, seg in enumerate(keep):
        s = f'{seg["s"] - seek_offset:.3f}'
        e = f'{seg["e"] - seek_offset:.3f}'
        parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    parts.append(f'{"".join(labels)}concat=n={len(keep)}:v=1:a=1[outv][outa]')
    return ";".join(parts)

def run(cmd: str, argv: list[str], dry_run: bool) -> None:
    if dry_run:
        quoted = " ".join(shlex.quote(a) if any(ch.isspace() or ch in '"\'' for ch in a) else a for a in argv)
        print(f"  $ {cmd} {quoted}")
        return
    r = subprocess.run([cmd, *argv])
    if r.returncode != 0:
        raise RuntimeError(f"{cmd} exited with {r.returncode}")

# ---------- CLI ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="curate", description="Split/trim a source video into chapter mp4s per edits.json.")
    p.add_argument("--config", type=Path, default=None,
                   help="Path to edits.json (default: ./edits.json)")
    p.add_argument("--input", type=Path, default=None,
                   help="Override source video (default: auto-detect from originals/)")
    p.add_argument("--only", default="",
                   help="Comma-separated filter: Ch## tag, title slug, or full filename")
    p.add_argument("--probe", action="store_true",
                   help="Print keep-segments per chapter, don't encode")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the ffmpeg plan without executing")
    p.add_argument("--no-yaml", action="store_true",
                   help="Skip writing the derived edits.yaml")
    return p

def main() -> None:
    args = build_parser().parse_args()

    config_path = (args.config or Path.cwd() / "edits.json").resolve()
    project_dir = config_path.parent
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise SystemExit(
            f'{config_path} must be a JSON object with at least a "chapters" array. '
            "(Legacy array-only format is no longer supported.)"
        )
    if not isinstance(config.get("chapters"), list):
        raise SystemExit(f'{config_path} must have a "chapters" array')

    naming_template = config.get("naming") or DEFAULT_NAMING
    output_dir_rel = config.get("output_dir") or DEFAULT_OUTPUT_DIR
    output_dir = (project_dir / output_dir_rel).resolve()
    yaml_out = project_dir / "edits.yaml"
    input_path = find_input(config, project_dir, str(args.input) if args.input else None)

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"config: {config_path}")
    print(f"input:  {input_path}")
    print(f"output: {output_dir}")
    print(f"naming: {naming_template}")
    if only:
        print(f"only:   {', '.join(only)}")
    print()

    processed = skipped = 0
    for idx, chapter in enumerate(config["chapters"]):
        name = chapter.get("name")
        start_ts = chapter.get("start_ts")
        end_ts = chapter.get("end_ts")
        cuts = chapter.get("cuts") or []
        if not name or not start_ts or not end_ts:
            print(f"! skipping chapter (missing name/start_ts/end_ts): {chapter}", file=sys.stderr)
            continue

        s_sec = ts_to_sec(start_ts)
        e_sec = ts_to_sec(end_ts)
        keep = compute_keep_segments(s_sec, e_sec, cuts)
        total_sec = sum(k["e"] - k["s"] for k in keep)
        out_filename = chapter_filename(naming_template, config.get("project"), idx, name, s_sec, e_sec, total_sec)

        if not should_process(name, idx, out_filename, only):
            skipped += 1
            continue

        print(f"▶ {out_filename}")
        print(f"  window: {sec_to_ts(s_sec)} → {sec_to_ts(e_sec)}  ({e_sec - s_sec:.2f}s)")
        if cuts:
            print(f"  cuts:   {len(cuts)} → keeping {len(keep)} segment(s), final {total_sec:.2f}s")
        for i, k in enumerate(keep):
            print(f"    keep {i + 1}: {sec_to_ts(k['s'])} → {sec_to_ts(k['e'])}  ({k['e'] - k['s']:.2f}s)")

        if args.probe:
            processed += 1
            print()
            continue

        out_file = output_dir / out_filename
        SEEK_PAD = 2.0
        seek_offset = max(0.0, s_sec - SEEK_PAD)
        filter_complex = build_filter_complex(keep, seek_offset)

        ffmpeg_args = [
            "-y", "-hide_banner", "-loglevel", "warning", "-stats",
            "-ss", f"{seek_offset:.3f}",
            "-i", str(input_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart",
            str(out_file),
        ]
        run("ffmpeg", ffmpeg_args, args.dry_run)
        processed += 1
        print(f"  ✓ wrote {out_file}")
        print()

    print(f"Done. processed={processed} skipped={skipped} total={len(config['chapters'])}")

    if not args.no_yaml:
        doc = build_derived_doc(
            config, input_path, project_dir,
            str(output_dir.relative_to(project_dir)) if output_dir.is_relative_to(project_dir) else str(output_dir),
            config["chapters"], naming_template,
        )
        if doc["warnings"]:
            print()
            for w in doc["warnings"]:
                print(f"  ⚠ {w}", file=sys.stderr)
        yaml_out.write_text(emit_yaml(doc), encoding="utf-8")
        print(f"\nyaml:   {yaml_out}")

if __name__ == "__main__":
    main()
