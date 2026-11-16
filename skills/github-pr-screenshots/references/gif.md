# Making a GIF with ffmpeg

Use these only when a GIF was asked for and what exists is a video or a set of frames. Write the GIF next to its
source, keep the source, and say in your report that you made the GIF and from what.

Check for ffmpeg with `ffmpeg -version`. If it is missing, report that and stop; do not install it.

## From a video

Two passes in one command: build a palette from the clip, then map the clip onto it. This looks far better than
ffmpeg's default GIF palette.

```bash
ffmpeg -i demo.mp4 \
  -vf "fps=12,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  -loop 0 demo.gif
```

- `fps=12`: 10 to 15 is smooth enough for UI and keeps the file small.
- `scale=800:-1`: the width in pixels; the height follows. A PR column is about 900 pixels wide, so wider
  rarely helps. Leave it out to keep the recording's own size.
- `-loop 0`: loop forever, as readers expect of a GIF.
- To use part of the clip, put `-ss 2 -t 6` (start at 2 s, keep 6 s) before `-i`.

## From frames

Frames play in filename order, so they must be zero-padded (`frame-000.png`, `frame-001.png`, …) and all the same
size.

```bash
ffmpeg -framerate 12 -pattern_type glob -i 'frames/*.png' \
  -vf "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  -loop 0 demo.gif
```

`-framerate` is the playback speed in frames per second (12 means about 83 ms per frame).

## Fitting under 10 MB

Check the size with `stat -c %s demo.gif` (10 MB is 10485760 bytes). If it is over, re-encode from the source with
these, one at a time, biggest saving first:

1. A shorter clip (`-ss`/`-t`), if the extra seconds aren't the point.
2. A lower width: `scale=640:-1`.
3. A lower frame rate: start the filter with `fps=8,`. It drops frames and keeps the playback speed, for video
   and frames alike.
4. Fewer colours: `palettegen=max_colors=128:stats_mode=diff`.

If it still does not fit, ask the user whether to attach the video instead.

## Check it

Look at a frame or two before uploading, and confirm the frame count and size:

```bash
ffmpeg -loglevel error -i demo.gif -vf "select=eq(n\,0)" -frames:v 1 first-frame.png
ffprobe -v error -count_frames -show_entries stream=nb_read_frames,width,height -of csv=p=0 demo.gif
```

The first-frame PNG is for looking at only. Upload the GIF.
