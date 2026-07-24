# Live2D Exporter

Krita plugin that prepares documents for Live2D export.

☺ Merges all layers that consist of only paint layers while maintaining group hierarchy
☺ Saves each visible top-level node into a conceptually matching PSD file

## Usage

Navigate to ☞ Tools › Scripts › Live2D Export.

## Installation

See the Krita documentation on how to install custom Python plugins.

## Requirements

- Krita 4.x or later
- PyQt5 (bundled with Krita)

## Output

Exported files are saved in the same folder as the current document, using sanitized top-level layer names as filenames.

## Troubleshooting

- Ensure your document is saved before exporting.
- Avoid duplicate top-level layer names.
- Ensure at least one top-level layer is visible.