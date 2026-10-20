# Focus Sound Studio audio

`rain.wav` is derived from **SV100344.ogg**, a rainfall field recording by **Shizhao** (July 2005).

- Source and public-domain dedication: https://commons.wikimedia.org/wiki/File:SV100344.ogg
- Original file: https://upload.wikimedia.org/wikipedia/commons/a/a0/SV100344.ogg
- License: public domain, released by the author (PD-self). The source grants use for any purpose without conditions where a public-domain dedication is not possible.
- Preparation: trimmed handling edges, collapsed duplicated stereo to mono, removed DC/rumble, band-limited and downsampled to 22050 Hz, adjusted level and softened isolated peaks. Saved as 16-bit PCM WAV, approximately 1.3 MB. Source hash and processing details are in `rain-source.json`.
- Runtime: resamples to the output rate, overlaps 0.75 seconds at the loop join, removes the duplicated overlap, and applies level matching. Playback is fully offline.

The other six sounds are generated locally. Noise power spectra follow 1/f^0 (white), 1/f^1 (pink) and 1/f^2 (brown), bounded below 25 Hz and gently rolled off above 16 kHz. The 432 Hz preset is a pure sine; binaural presets use 220/230 Hz and 220/260 Hz on separate channels. These are sound descriptions, without promises of cognitive or medical effects. Stereo headphones preserve the binaural channel separation.

Generated buffers last 20 seconds and are cached only when requested. Gain changes ramp over 20 ms; stopping waits briefly for the ramp on the audio worker. Imported user recordings remain unchanged.
