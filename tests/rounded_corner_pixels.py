"""Check native captures against source-over compositing of opaque coverage."""

import json
import sys
from pathlib import Path

from PIL import Image


def pixels(image):
    values = iter(image.tobytes())
    return zip(values, values, values)


def same_rendering(left, right):
    # Separate GPU draws can round antialiased edge channels by one byte.
    return all(abs(a - b) <= 1 for a, b in zip(left.tobytes(), right.tobytes()))


def validate(directory):
    data = json.loads((directory / "result.json").read_text())
    assert data["passed"], data
    checked = legacy_errors = 0
    for scale in data["scales"]:
        for background in data["backgrounds"]:
            prefix = directory / f"scale-{scale}-bg-{background}"
            opaque = Image.open(f"{prefix}-opaque.png").convert("RGB")
            actual = Image.open(f"{prefix}-alpha.png").convert("RGB")
            for case in data["cases"]:
                x, y, w, h = (case[key] for key in ("x", "y", "width", "height"))
                alpha = case["alpha"]
                control = opaque.crop((x, y, x + w, y + h))
                old_control = opaque.crop((x + 84, y, x + 84 + w, y + h))
                assert same_rendering(control, old_control), "opaque rendering changed"
                new = actual.crop((x, y, x + w, y + h))
                old = actual.crop((x + 84, y, x + 84 + w, y + h))
                if alpha in (0, 1) or case["radius"] == 0:
                    assert same_rendering(new, old), "opaque/square control changed"
                samples = zip(pixels(control), pixels(new), pixels(old))
                for reference, pixel, legacy in samples:
                    expected = [background + alpha * (c - background) for c in reference]
                    error = max(abs(a - b) for a, b in zip(pixel, expected))
                    assert error <= 2, (scale, background, case, pixel, expected, error)
                    legacy_errors += max(abs(a - b) for a, b in zip(legacy, expected)) > 2
                    checked += 1
    assert legacy_errors > 0, "captures did not exercise the original defect"
    return {"passed": True, "pixels_checked": checked, "legacy_pixel_failures": legacy_errors}


if __name__ == "__main__":
    print(json.dumps(validate(Path(sys.argv[1]))))
