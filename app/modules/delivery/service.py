from .checks import verify

CODES = {'MISSING': '必填字段缺失', 'WIDTH': '列数不符', 'CUE_CONFLICT': '同轨同号内容冲突',
         'CUE_COPY': '相同字幕副本', 'TIME_LABEL': '时码格式无效', 'DROPPED_LABEL': '该帧号已跳过',
         'TIME_ORDER': '出点不晚于入点', 'OVERLAP': '同轨目标帧相交', 'GAP': '缺少切版记录',
         'DWELL_OK': '停留达标', 'DWELL_EXTEND': '同画面可补足', 'DWELL_RECUT': '退回重切'}


def signing(record):
    # 证据包必须可下载复核：散列失配才拒发，停留未过只在证书与页面上标记不可签发。
    from app.digests import digest, encode, fingerprints
    from app.problems import Rejection
    stamp = record['manifest']
    if (fingerprints(record['original']) != stamp['input_sha256'] or
            digest(encode(record['stages'])) != stamp['result_sha256'] or
            not record['stages']['source']['counts']['balanced'] or
            not record['stages']['balance']['balanced']):
        raise Rejection('INVALID_EVIDENCE', '证据散列或覆盖勾稽不符', 409)
    dwell = record['stages']['dwell']
    return dict(verified=dwell['passed'], certificate=stamp if dwell['passed'] else None,
                **record, reason_codes=CODES)
