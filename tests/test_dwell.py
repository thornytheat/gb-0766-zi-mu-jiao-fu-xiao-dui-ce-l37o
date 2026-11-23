from app.material import example
from app.modules.dwell.service import assess
from app.pipeline import inspect


def short(stages, cue_id):
    return [row for row in stages['dwell']['rows'] if row['cue_id'] == cue_id]


def test_half_second_threshold_is_twelve_target_frames():
    stages = inspect(example('dirty'))
    assert stages['dwell']['counts']['min_dwell_frames'] == 12


def test_each_keep_fragment_carries_target_span_and_dwell(dirty):
    rows = dirty['dwell']['rows']
    assert len(rows) == dirty['dwell']['counts']['kept_fragments'] == 16
    c108, = [row for row in rows if row['cue_id'] == 'C108']
    assert (c108['frame_in'], c108['frame_out'], c108['dwell_frames'], c108['code']) == \
           (2457, 2469, 12, 'DWELL_OK')


def test_extend_within_same_kept_shot_proposes_twelve_frames(dirty):
    c104, = short(dirty, 'C104')
    assert c104['code'] == 'DWELL_EXTEND'
    assert c104['cut'] == 'B-01' and c104['line'] == 5 and c104['cut_line'] == 4
    assert (c104['proposed_frame_in'], c104['proposed_frame_out']) == (1291, 1303)
    # 建议区间留在原保留画面 B-01 的目标帧跨度内。
    assert c104['cut_frame_in'] <= c104['proposed_frame_in'] < c104['proposed_frame_out'] <= c104['cut_frame_out']
    # 不压住相邻字幕：左为 C102 出点 1011，右为 C103 入点 1371。
    assert (c104['left_limit'], c104['right_limit']) == ('1011', '1371')
    assert c104['left_with'] == 'C102@原行3' and c104['right_with'] == 'C103@原行4'


def test_extend_in_place_when_right_side_is_open(dirty):
    c115, = short(dirty, 'C115')
    assert c115['code'] == 'DWELL_EXTEND'
    # C116 入点 2601 与本句出点首尾相接，半开区间不算占用，原地向右补足 12 帧。
    assert (c115['proposed_frame_in'], c115['proposed_frame_out']) == (2593, 2605)
    assert c115['right_with'] is None

def test_recut_traces_original_line_and_cut_point(dirty):
    c118, = short(dirty, 'C118')
    assert c118['code'] == 'DWELL_RECUT'
    assert (c118['line'], c118['cue_id'], c118['cut'], c118['cut_line']) == (22, 'C118', 'A-01', 2)
    assert c118['proposed_frame_in'] is None and c118['proposed_frame_out'] is None
    # 退回原因可复核：可用画面被同轨 C101 两侧夹住，延任何方向都会压字幕。
    assert c118['left_with'] == c118['right_with'] == 'C101@原行2'
    assert int(c118['right_limit']) - int(c118['left_limit']) < 12


def test_dirty_sample_dwell_verdict(dirty):
    counts = dirty['dwell']['counts']
    assert counts == dict(kept_fragments=16, dwell_ok=11, extend_within_shot=2,
                          recut_required=3, min_dwell_frames=12)
    assert dirty['dwell']['passed'] is False
    assert {row['cue_id'] for row in dirty['dwell']['rows'] if row['code'] == 'DWELL_RECUT'} == \
           {'C117', 'C118', 'C119'}


def test_clean_sample_passes_dwell():
    stages = inspect(example('clean'))
    assert stages['dwell']['passed'] is True
    assert stages['dwell']['counts']['recut_required'] == 0
    assert all(row['code'] == 'DWELL_OK' for row in stages['dwell']['rows'])


def test_touching_neighbor_does_not_block_extension():
    # 目标 [10,18) 仅 8 帧；同轨另一字幕从 18 帧相接（半开区间不算占用），
    # 画面右界为 21，可原地向右延到 [10,22) 之内的 [9,21) 判定由可用宽度决定。
    fragments = [
        dict(kind='KEEP', track='t', line=1, cue_id='X', cut='K1', cut_line=2, frame_in=10, frame_out=18),
        dict(kind='KEEP', track='t', line=3, cue_id='Y', cut='K1', cut_line=2, frame_in=18, frame_out=40),
    ]
    cuts = [dict(cut='K1', kind='KEEP', start=0, end=25, target=0, line=2)]
    row, = [item for item in assess(fragments, cuts)['rows'] if item['cue_id'] == 'X']
    assert row['code'] == 'DWELL_EXTEND'
    assert (row['proposed_frame_in'], row['proposed_frame_out']) == (9, 21)
    assert row['right_with'] is None and row['left_with'] is None


def test_shot_shorter_than_half_second_forces_recut():
    fragments = [dict(kind='KEEP', track='t', line=1, cue_id='X', cut='K1', cut_line=2,
                      frame_in=5, frame_out=9)]
    cuts = [dict(cut='K1', kind='KEEP', start=0, end=10, target=0, line=2)]
    row, = assess(fragments, cuts)['rows']
    assert row['code'] == 'DWELL_RECUT' and row['available_frames'] == 9
    assert (row['left_limit'], row['right_limit']) == ('0', '9')
