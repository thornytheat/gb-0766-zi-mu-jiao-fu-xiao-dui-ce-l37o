import pytest
from app.modules.delivery.service import signing
from app.problems import Rejection


@pytest.fixture
def clean_run(client):
    return client.post('/api/runs', json={'sample': 'clean'}).json


def test_download(client, saved):
    response = client.get(f"/api/delivery/{saved['id']}/export")
    assert 'attachment;' in response.headers['Content-Disposition']
    assert response.json['original']['cues'].startswith('﻿legacy_id')


def test_export_keeps_recut_judgements_for_review(client, saved):
    # 存在退回重切段时证据包仍可下载，停留判断完整可复核，但不予签发。
    payload = client.get(f"/api/delivery/{saved['id']}/export").json
    assert payload['verified'] is False and payload['certificate'] is None
    dwell = payload['stages']['dwell']
    assert dwell['counts']['recut_required'] == 3 and dwell['passed'] is False
    assert {row['cue_id'] for row in dwell['rows'] if row['code'] == 'DWELL_RECUT'} == \
           {'C117', 'C118', 'C119'}


def test_clean_run_is_signable(client, clean_run):
    payload = client.get(f"/api/delivery/{clean_run['id']}/export").json
    assert payload['verified'] is True and payload['certificate'] == clean_run['manifest']
    assert client.get(f"/api/delivery/{clean_run['id']}").json['certificate'] == clean_run['manifest']


def test_recut_run_refuses_certificate(client, saved):
    response = client.get(f"/api/delivery/{saved['id']}")
    assert (response.status_code, response.json['code']) == (409, 'DWELL_RECUT')


def test_archive_stamp(client, clean_run):
    assert client.get(f"/api/delivery/{clean_run['id']}").json['certificate'] == clean_run['manifest']


def test_unknown_delivery(client):
    assert client.get('/api/delivery/none/export').json['code'] == 'NO_RUN'


def test_mutated_original(client, saved):
    entry = client.application.extensions['cut_archive'].read(saved['id'])
    entry['original']['cuts'] += '\n'
    with pytest.raises(Rejection, match='证据散列'):
        signing(entry)


def test_mutated_result(client, saved):
    entry = client.application.extensions['cut_archive'].read(saved['id'])
    entry['stages']['overlaps']['rows'].clear()
    with pytest.raises(Rejection, match='证据散列'):
        signing(entry)


def test_precision_survives_roundtrip(client, saved):
    response = client.get(f"/api/delivery/{saved['id']}/export").json
    assert response['stages']['overlaps']['rows'][-1]['cues'][0] == '9007199254740993'
