# MoviePy v1 to v2 Migration Guide

## Key Breaking Changes

### Method Name Changes

| v1.x | v2 |
|------|-----|
| `.set_duration(t)` | `.with_duration(t)` |
| `.set_fps(fps)` | `.with_fps(fps)` |
| `.set_audio(audio)` | `.with_audio(audio)` |
| `.set_position(pos)` | `.with_position(pos)` |
| `.volumex(factor)` | `.with_volume_scaled(factor)` |
| `.subclip(t1, t2)` | `.subclipped(t1, t2)` |
| `.fl_image(func)` | `.image_transform(func)` |
| `.fl_time(func)` | `.time_transform(func)` |

### Effects Application
```python
# v1.x
from moviepy.editor import *
clip = clip.fx(vfx.fadein, 1.0).fx(vfx.fadeout, 1.0)

# v2
from moviepy import VideoFileClip
from moviepy.video.fx import fadein, fadeout
clip = clip.with_effects([fadein(1.0), fadeout(1.0)])
```

### Import Changes
```python
# v1.x
from moviepy.editor import *

# v2 (preferred)
from moviepy import *
# Or specific imports
from moviepy import VideoFileClip, TextClip, CompositeVideoClip
```

### Composite Video Changes
```python
# v1.x
from moviepy.editor import CompositeVideoClip
composite = CompositeVideoClip([clip1, clip2.set_position(("center", "center"))])

# v2
from moviepy import CompositeVideoClip
composite = CompositeVideoClip([clip1, clip2.with_position(("center", "center"))])
```

### Audio Changes
```python
# v1.x
clip.audio.volumex(0.5)

# v2
clip.audio.with_volume_scaled(0.5)
```

## Migration Checklist

1. ✅ Update all `.set_*()` methods to `.with_*()`
2. ✅ Change `.subclip()` to `.subclipped()`
3. ✅ Update `.volumex()` to `.with_volume_scaled()`
4. ✅ Change effects from `.fx()` to `.with_effects([])`
5. ✅ Update imports from `moviepy.editor` to `moviepy`
6. ✅ Review method chaining (all `.with_*()` return new clips)
7. ✅ Update `.fl_*` methods to `.*_transform()`
8. ✅ Test thoroughly - v2 may have subtle behavior changes

## Common Patterns

### Before (v1.x)
```python
from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.video.fx import all as vfx

clip = VideoFileClip("video.mp4")
clip = clip.subclip(0, 10)
clip = clip.fx(vfx.fadein, 1.0)
clip = clip.set_audio(clip.audio.volumex(0.5))
clip.write_videofile("output.mp4")
```

### After (v2)
```python
from moviepy import VideoFileClip, concatenate_videoclips
from moviepy.video.fx import fadein

clip = VideoFileClip("video.mp4")
clip = clip.subclipped(0, 10)
clip = clip.with_effects([fadein(1.0)])
clip = clip.with_audio(clip.audio.with_volume_scaled(0.5))
clip.write_videofile("output.mp4")
```

## Why the Changes?

v2 adopts a more functional, immutable approach:
- `.with_*()` methods return **new clips** (don't modify originals)
- More consistent naming conventions
- Better composability with effects chains
- Clearer intent and reduced side effects
