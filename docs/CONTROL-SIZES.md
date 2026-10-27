# Shared control sizes

Focus and Media use the same `ui/metrics.py` sizing rules. Sizes are logical pixels; CustomTkinter applies Windows DPI scaling once.

| Role | Height | Text size |
| --- | ---: | ---: |
| Standard button / field | 36 | 13 |
| Compact toolbar control | 32 | 12 |
| Large field / header control | 40 | 13 |
| Primary action | 44 | 14 |
| Navigation | 47 | 14 |
| Navigation in a small window | 38 | 13 |
| Page title | — | 30 |

Navigation uses the same 736-pixel window-height breakpoint in both apps. Media's persistent playback bar no longer independently forces compact navigation. Header height is 76 and sidebar width is 232 in both apps. Numeric displays, icons and small inline controls retain role-appropriate dimensions.

Validation: Focus's nine-screen UI smoke test passed in light/dark, including responsive modes, dialogs, mini-player and workspace lifecycle. Media's 20 UI cases passed in light/dark at 900×600 and 1240×800. `SIZING-CHECK.json` records actual navigation row measurements and visible sidebar footers in both apps at normal, minimum and restored window sizes.

The independent sizing review found no blocking layout regression. Its remaining Focus outliers were aligned as well: Blocker fields/actions use the 40-pixel large-control role, Sound card actions use 36 pixels, and the guide's primary close action uses 44 pixels with 14-pixel text.
