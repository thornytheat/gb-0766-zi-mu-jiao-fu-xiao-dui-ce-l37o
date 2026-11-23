def test_every_sheet(client, saved):
    for sheet, text in [('source', '提交供应商原件'), ('clock', '该帧号已跳过'), ('edits', 'B-01'),
                        ('overlaps', '同轨目标帧相交'), ('dwell', '退回重切'), ('balance', '740'),
                        ('runs', '复算该版'), ('delivery', '下载交付证据')]:
        response = client.get(f'/sheet/{sheet}?run={saved["id"]}')
        assert response.status_code == 200 and text in response.get_data(as_text=True)


def test_delivery_page_reports_withhold_but_keeps_download(client, saved):
    html = client.get(f'/sheet/delivery?run={saved["id"]}').get_data(as_text=True)
    assert '不予签发' in html and '下载交付证据' in html


def test_dwell_sheet_renders_judgement_columns(client, saved):
    html = client.get(f'/sheet/dwell?run={saved["id"]}').get_data(as_text=True)
    assert '停留帧' in html and '可延右界' in html and '建议出帧' in html


def test_dwell_stage_api(client):
    result = client.get('/api/check/dwell?sample=dirty').json
    assert result['counts']['recut_required'] == 3 and result['passed'] is False
    assert client.get('/api/check/dwell?sample=clean').json['passed'] is True


def test_sheet_cells_focusable(client):
    html = client.get('/').get_data(as_text=True)
    assert 'tabindex="0" data-cell="A1"' in html
    assert 'tabindex="-1" data-cell="B1"' in html


def test_unknown_sheet(client):
    response = client.get('/api/check/unknown')
    assert (response.status_code, response.json['code']) == (404, 'NO_SHEET')
