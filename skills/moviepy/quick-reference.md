# MoviePy v2 Quick Reference

## Installation
```bash
pip install moviepy
# With optional dependencies
pip install moviepy[optional]
```

## Essential Imports
```python
from moviepy import *
# Or specific imports:
from moviepy import VideoFileClip, AudioFileClip, TextClip
from moviepy import CompositeVideoClip, concatenate_videoclips
from moviepy.video.fx import fadein, fadeout, resize, rotate
from moviepy.audio.fx import audio_fadein, audio_fadeout
```

## Common Patterns

### Load & Export
```python
# Load video
clip = VideoFileClip("input.mp4")

# Export video
clip.write_videofile("output.mp4", fps=30, codec="libx264")

# Export GIF
clip.write_gif("output.gif", fps=10)
```

### Time Operations
```python
# Trim
clip.subclipped(5, 15)  # seconds 5 to 15

# Set duration
clip.with_duration(10)

# Loop
clip.loop(n=3)  # repeat 3 times
```

### Audio
```python
# Remove audio
clip.without_audio()

# Replace audio
clip.with_audio(AudioFileClip("music.mp3"))

# Adjust volume
clip.with_audio(clip.audio.with_volume_scaled(0.5))  # 50% volume
```

### Compositing
```python
# Layer clips
CompositeVideoClip([
    background_clip,
    overlay_clip.with_position(("center", "center"))
])

# Concatenate clips
concatenate_videoclips([clip1, clip2, clip3])
```

### Text
```python
TextClip(
    text="Hello World",
    font="Arial",
    font_size=70,
    color="white",
    bg_color="black",
    duration=5
).with_position(("center", "bottom"))
```

### Effects Chain
```python
clip.with_effects([
    fadein(1.0),
    resize(width=1920),
    fadeout(1.0)
])
```

### Positioning
```python
# Positions can be:
.with_position((x, y))           # Pixel coordinates
.with_position(("center", "center"))
.with_position(("left", "top"))
.with_position(("right", "bottom"))
```

## Performance Tips
- Use `.subclipped()` for testing
- Set `threads=4` in `write_videofile()`
- Lower `fps` for GIFs (10-15 fps)
- Close clips with `.close()` to free memory

## Common Video Codecs
- `codec="libx264"` - H.264 (most compatible)
- `codec="libx265"` - H.265 (better compression)
- `codec="libvpx"` - VP8 for WebM
- `audio_codec="aac"` - AAC audio (most compatible)

## Troubleshooting
- **FFmpeg not found**: Install FFmpeg system-wide
- **Text rendering fails**: Install ImageMagick
- **Memory issues**: Close clips, use smaller sections
- **v1 → v2 migration**: Check method names (many changed)
