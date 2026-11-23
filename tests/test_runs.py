from concurrent.futures import ThreadPoolExecutor
from app.main import create_app
from app.material import example
from app.modules.runs.files import CutArchive
from app.modules.runs.service import record


def test_repeat(client, saved):
    result = client.post(f"/api/runs/{saved['id']}/repeat").json
    assert result['reused'] and result['manifest'] == saved['manifest']


def test_restart(client, saved, tmp_path):
    again = create_app(tmp_path).test_client().get(f"/api/runs/{saved['id']}")
    assert again.json['counts']['delivered'] == '740'
    assert again.json['manifest'] == saved['manifest']


def test_bad_payload(client):
    outcome = client.post('/api/runs', json={'cues':'only'})
    assert (outcome.status_code, outcome.json['code']) == (422,'PAYLOAD')


def test_failed_cut_never_published(client):
    bad = dict(example('dirty'), cuts='')
    assert client.post('/api/runs', json=bad).status_code == 422
    assert client.get('/api/runs').json['count'] == 0


def test_parallel(tmp_path):
    archive = CutArchive(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        items = list(pool.map(lambda _: record(archive, example('dirty')), range(4)))
    assert sum(not item['reused'] for item in items) == 1
    assert len(tuple(tmp_path.iterdir())) == 1


def test_different_files(client, saved):
    result = client.post('/api/runs', json={'sample':'clean'}).json
    assert result['id'] != saved['id']
    assert client.get('/api/runs').json['count'] == 2


def test_same_files_repeat_never_adds_conclusion(client, saved):
    again = client.post('/api/runs', json={'sample': 'dirty'}).json
    assert again['id'] == saved['id'] and again['reused'] is True
    assert client.get('/api/runs').json['count'] == 1


def test_changed_cuts_invalidate_old_conclusion_and_recompute(client, saved):
    # 旧档结论保持原样：仍有三条退回重切。
    old = client.application.extensions['cut_archive'].read(saved['id'])
    assert old['stages']['dwell']['counts']['recut_required'] == 3
    # 切点变化后内容散列不同，必须另立档号、按新切版全量重算，不覆盖旧结论。
    recut = dict(example('dirty'))
    recut['cuts'] = (
        'cut,start,end,target,kind\n'
        'A-01,0,1300,0,KEEP\n'
        'B-01,1300,2000,1042,KEEP\n'
        'B-02,2200,4000,1603,KEEP\n'
    )
    new = client.post('/api/runs', json=recut).json
    assert new['id'] != saved['id'] and new['reused'] is False
    new_entry = client.application.extensions['cut_archive'].read(new['id'])
    assert new_entry['manifest']['result_sha256'] != saved['manifest']['result_sha256']
    # 保留画面数从 16 段变为 17 段，证明按新切点重算；旧档结论原样保留。
    assert new_entry['stages']['dwell']['counts']['kept_fragments'] == 17
    assert client.get('/api/runs').json['count'] == 2
    assert client.application.extensions['cut_archive'].read(saved['id'])['stages'] == old['stages']


def test_widening_cut_flips_recut_to_extendable(tmp_path):
    from app.modules.runs.files import CutArchive
    from app.modules.runs.service import record
    cues = ('cue_id,track,format,in,out,text\n'
            'C1,简中,FRAME,0,10,短句一闪\n'
            'C2,简中,FRAME,100,120,后一句字幕\n')
    narrow = dict(cues=cues, cuts='cut,start,end,target,kind\nK1,0,12,0,KEEP\nK2,100,120,20,KEEP\n')
    store = CutArchive(tmp_path)
    first = record(store, narrow)
    first_entry = store.read(first['id'])
    row, = [item for item in first_entry['stages']['dwell']['rows'] if item['cue_id'] == 'C1']
    assert row['code'] == 'DWELL_RECUT' and row['cut'] == 'K1'
    # 退回重切：K1 放宽到源 30 帧，目标画面足够 12 帧且不压后一句。
    widened = dict(cues=cues,
                   cuts='cut,start,end,target,kind\nK1,0,30,0,KEEP\nK2,100,120,25,KEEP\n')
    second = record(store, widened)
    assert second['id'] != first['id']
    second_row, = [item for item in store.read(second['id'])['stages']['dwell']['rows']
                   if item['cue_id'] == 'C1']
    assert second_row['code'] == 'DWELL_EXTEND'
    assert second_row['proposed_frame_out'] - second_row['proposed_frame_in'] == 12
    # 旧档结论未被改写。
    assert store.read(first['id'])['stages']['dwell']['rows'][0]['code'] == 'DWELL_RECUT'
