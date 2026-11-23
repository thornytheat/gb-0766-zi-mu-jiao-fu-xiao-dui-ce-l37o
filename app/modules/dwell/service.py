"""停留时长校核：24 fps 目标上每句字幕至少保留半秒（12 个交付整数帧）。

逐段检查落在 KEEP 切段内的字幕片段，先给目标帧区间，再判定能否在同一保留
画面（同一 KEEP 切段的目标区间）内把停留补足到门槛；补足会与同轨相邻字幕
相撞、或切段本身不够 12 帧的，追到原行与切点退回重切。
"""
from fractions import Fraction
from math import ceil
from app.modules.clock.timecode import RATIO
from app.rational import show
from app.settings import MIN_DWELL_FRAMES

OK = 'DWELL_OK'
EXTEND = 'DWELL_EXTEND'
RECUT = 'DWELL_RECUT'


def assess(fragments, cuts):
    keeps = [row for row in fragments if row['kind'] == 'KEEP']
    envelopes = {cut['cut']: envelope(cut) for cut in cuts if cut['kind'] == 'KEEP'}
    by_track = {}
    for row in keeps:
        by_track.setdefault(row['track'], []).append(row)
    rows = [judge(row, envelopes[row['cut']], by_track.get(row['track'], [])) for row in keeps]
    counts = dict(kept_fragments=len(rows),
                  dwell_ok=sum(row['code'] == OK for row in rows),
                  extend_within_shot=sum(row['code'] == EXTEND for row in rows),
                  recut_required=sum(row['code'] == RECUT for row in rows),
                  min_dwell_frames=MIN_DWELL_FRAMES)
    return dict(rows=rows, counts=counts, passed=counts['recut_required'] == 0)


def envelope(cut):
    """KEEP 切段目标整数帧跨度 [lo, hi)，即该保留画面内能容纳的全部交付帧。"""
    hi = Fraction(cut['target']) + (cut['end'] - cut['start']) * RATIO
    return cut['target'], ceil(hi)


def judge(row, span, track_rows):
    frame_in, frame_out = row['frame_in'], row['frame_out']
    lo, hi = span
    result = dict(line=row['line'], cue_id=row['cue_id'], track=row['track'], cut=row['cut'],
                  cut_line=row['cut_line'], frame_in=frame_in, frame_out=frame_out,
                  dwell_frames=frame_out - frame_in,
                  cut_frame_in=lo, cut_frame_out=hi, available_frames=hi - lo)
    if frame_out - frame_in >= MIN_DWELL_FRAMES:
        result.update(code=OK, left_limit=show(lo), right_limit=show(hi),
                      left_with=None, right_with=None,
                      proposed_frame_in=frame_in, proposed_frame_out=frame_out)
        return result
    # 同轨其他字幕对可延展边界的占用（半开区间；首尾相接不算占用）。
    left_block, right_block = lo, hi
    left_with = right_with = None
    for other in track_rows:
        if other is row or other['cue_id'] == row['cue_id']:
            continue
        other_in, other_out = other['frame_in'], other['frame_out']
        if other_out <= frame_in:
            if other_out > left_block:
                left_block, left_with = other_out, other
        elif other_in >= frame_out:
            if other_in > frame_out and other_in < right_block:
                right_block, right_with = other_in, other
        else:
            # 与同轨字幕交叠本身已在冲突页登记，停留无法在不压字幕的情况下补足。
            left_block, right_block, left_with, right_with = frame_in, frame_out, other, other
            break
    result.update(left_limit=show(left_block), right_limit=show(right_block),
                  left_with=blocker(left_with), right_with=blocker(right_with))
    if right_block - left_block >= MIN_DWELL_FRAMES:
        proposed_in, proposed_out = proposal(frame_in, frame_out, left_block, right_block)
        result.update(code=EXTEND, proposed_frame_in=proposed_in, proposed_frame_out=proposed_out)
    else:
        result.update(code=RECUT, proposed_frame_in=None, proposed_frame_out=None)
    return result


def blocker(row):
    return None if row is None else f"{row['cue_id']}@原行{row['line']}"


def proposal(frame_in, frame_out, left_block, right_block):
    """保留原入点优先向右延；右界不够再整体左移，保证落点始终在可用画面内。"""
    if frame_in + MIN_DWELL_FRAMES <= right_block:
        return frame_in, frame_in + MIN_DWELL_FRAMES
    return right_block - MIN_DWELL_FRAMES, right_block
