from pathlib import Path

from fractions import Fraction

SAMPLE_ROOT = Path(__file__).resolve().parent.parent / 'sample_data'
VERSION = 'venue-captions/1'
# 审查要求：每句字幕在 24 fps 目标上至少停留半秒，即 24 × 1/2 = 12 个交付整数帧。
MIN_DWELL_FRAMES = 12
MIN_DWELL_SECONDS = Fraction(1, 2)
