"""Next-version common controller: explicit visible citation registry and errors."""
import copy
import json
import time
from rca.common import compact, redact
from rca.context import present_evidence
from research.spec import FINAL_TOOL, SCHEMA, SYSTEM, STOP_GUIDANCE


def validate_schema(value, schema, path='$'):
    kind = schema['type']
    if kind == 'object':
        if not isinstance(value, dict) or set(value) != set(schema['required']):
            raise ValueError(path+': output fields mismatch')
        for key, sub in schema['properties'].items():
            validate_schema(value[key], sub, path+'.'+key)
    elif kind == 'array':
        if not isinstance(value, list) or len(value) > 24:
            raise ValueError('invalid array')
        for index,item in enumerate(value):
            validate_schema(item, schema['items'],path+f'[{index}]')
    elif kind == 'string':
        if not isinstance(value, str) or len(value) > 2000:
            raise ValueError(path+': expected string of at most 2000 characters, got '+type(value).__name__)
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError('invalid enum')


def citation_registry(evidence):
    registry={}
    def visit(value):
        if isinstance(value,dict):
            if isinstance(value.get('evidence_id'),str) and 'tool' in value:
                key=value['evidence_id']
                if key in registry and registry[key]!=value:raise ValueError('ambiguous evidence ID')
                registry[key]=value
            for item in value.values():visit(item)
        elif isinstance(value,list):
            for item in value:visit(item)
    visit(evidence)
    return registry


def validate_answer(value, evidence):
    validate_schema(value, SCHEMA)
    if value['confirmed_cause'].strip().lower() == 'null':
        raise ValueError('use empty string for absent confirmed cause, not literal null')
    known = citation_registry(evidence)
    for claim in value['claims']:
        if not claim['text'].strip() or not claim['evidence_ids'] or any(i not in known for i in claim['evidence_ids']):
            raise ValueError('claim needs nonempty text and actually shown evidence IDs; unknown='+str([i for i in claim['evidence_ids'] if i not in known]))
    if value['confirmed_cause'] and not any(c['kind'] == 'observation' and any(
            known[i].get('availability') == 'available' for i in c['evidence_ids']) for c in value['claims']):
        raise ValueError('confirmed cause requires available cited observation; semantics still require human review')
    return value


def source_key(e):
    if 'source_key' in e:
        return e['source_key']
    if e['tool'] == 'get_metrics':
        return 'metrics_memory' if 'working_set_bytes' in e.get('series', {}) else 'metrics_cpu'
    return e['tool']


def run_case(case, config, provider, limits, record):
    # Only public incident/evidence are accepted. Truth cannot accidentally be
    # serialized by passing an entire fixture to a prompt.
    if set(case) != {'case_id', 'incident', 'evidence'}:
        raise ValueError('public case fields must be exactly case_id/incident/evidence')
    catalog = {source_key(e): e for e in case['evidence'] if config['ebpf'] or e['tool'] != 'get_ebpf_summary'}
    if len(catalog) != len([e for e in case['evidence'] if config['ebpf'] or e['tool'] != 'get_ebpf_summary']):
        raise ValueError('ambiguous public source snapshot')
    shown, queried, seen_for_bytes = [], [], set()
    errors, calls, repairs, rounds, tool_count, chars_total = [], 0, 0, 0, 0, 0
    started = time.monotonic()
    result = {'case_id': case['case_id'], 'state': 'error', 'answer': None, 'attempts': [],
              'retrievals': [], 'normalizations': [], 'claims_trace': [], 'error': None}

    def retrieve(key):
        nonlocal tool_count
        if tool_count >= limits['tool_calls']:
            raise ValueError('tool budget exhausted')
        tool_count += 1
        duplicate = key in queried
        result['retrievals'].append({'source': key, 'duplicate': duplicate,
                                     'executed': not (duplicate and config.get('dedup', True))})
        queried.append(key)
        if not duplicate or not config.get('dedup', True):
            e = copy.deepcopy(catalog[key])
            shown.append(present_evidence(e, case['incident'], 'compact-v4' if config.get('compression', True) else 'full-v4'))
        # Ledger always preserves one copy per evidence ID in every arm.
        shown[:] = list({e['evidence_id']: e for e in shown}.values())

    if not config['selective']:
        for key in catalog:
            retrieve(key)
    repairing = False
    try:
        while calls < limits['calls_per_run']:
            remaining = limits['seconds_per_run'] - (time.monotonic() - started)
            if remaining <= 0:
                raise ValueError('per-run time budget exhausted')
            final_only = repairing or not config['selective'] or rounds >= limits['retrieval_rounds'] or tool_count >= limits['tool_calls']
            tools = [copy.deepcopy(FINAL_TOOL)]
            if not final_only:
                names = [k for k in catalog if not config.get('dedup', True) or k not in queried]
                if names:
                    tools.insert(0, {'type': 'function', 'function': {'name': 'inspect', 'description': 'Read selected incident-time telemetry snapshots.',
                        'parameters': {'type': 'object', 'additionalProperties': False, 'properties': {
                            'sources': {'type': 'array', 'items': {'type': 'string', 'enum': names}}}, 'required': ['sources']}}})
            ledger = {'incident': case['incident'], 'evidence': shown, 'errors': errors,
                      'instruction': 'Submit final now; no new evidence.' if final_only else 'Select useful sources or submit.'}
            messages = [{'role': 'system', 'content': SYSTEM + '\nNested historical evidence IDs may be cited, but retain their original target and time. hypotheses and unknowns contain strings only. Source keys identify telemetry type and workload; availability and relevance require inspection.\n' + (STOP_GUIDANCE if config.get('stop_guidance', True) else '')},
                        {'role': 'user', 'content': compact(ledger)}]
            payload = provider.payload(messages, tools)
            request_chars = len(compact(payload))
            if request_chars > limits['request_chars'] or chars_total + request_chars > limits['cumulative_chars']:
                raise ValueError('per-run input budget exhausted')
            chars_total += request_chars
            categories = {'new_evidence_bytes': 0, 'repeated_evidence_bytes': 0}
            for e in shown:
                field = 'repeated_evidence_bytes' if e['evidence_id'] in seen_for_bytes else 'new_evidence_bytes'
                categories[field] += len(compact(e).encode())
                seen_for_bytes.add(e['evidence_id'])
            categories['total_request_bytes'] = len(compact(payload).encode())
            categories['other_request_bytes'] = categories['total_request_bytes'] - categories['new_evidence_bytes'] - categories['repeated_evidence_bytes']
            phase = 'repair' if repairing else ('final' if final_only else 'selection_or_final')
            record({'type': 'request', 'call': calls + 1, 'phase': phase, 'payload': payload, 'byte_attribution': categories})
            calls += 1
            try:
                answer = provider.complete(messages, tools, min(60, remaining))
            except Exception as exc:
                result['global_stop'] = True
                raise RuntimeError('provider_or_global_budget:' + type(exc).__name__) from None
            choices = answer.get('choices', [])
            public = {k:answer[k] for k in ('id', 'model', 'provider', 'usage') if k in answer}
            public['choices'] = [{'finish_reason': c.get('finish_reason'), 'message': {
                k:v for k,v in c.get('message', {}).items() if k in ('role', 'content', 'tool_calls')}} for c in choices]
            record({'type': 'response', 'call': calls, 'phase': phase, 'response': redact(public)})
            attempt = {'call': calls, 'phase': phase, 'usage': answer.get('usage', {}), 'byte_attribution': categories}
            result['attempts'].append(attempt)
            try:
                choice = choices[0]
                if choice.get('finish_reason') == 'length':
                    raise ValueError('output truncated')
                msg = choice['message']
                tool_calls = msg.get('tool_calls', [])
                if len(tool_calls) == 1 and tool_calls[0]['function']['name'] == 'inspect' and not final_only:
                    args = json.loads(tool_calls[0]['function']['arguments'])
                    if set(args) != {'sources'} or not isinstance(args['sources'], list) or not args['sources'] or any(k not in catalog for k in args['sources']):
                        raise ValueError('invalid inspection request')
                    rounds += 1
                    for key in args['sources']:
                        retrieve(key)
                    attempt['kind'] = 'retrieval'
                    continue
                if len(tool_calls) == 1 and tool_calls[0]['function']['name'] == 'submit_rca':
                    raw = tool_calls[0]['function']['arguments']
                elif not tool_calls:
                    raw = msg.get('content', '')
                else:
                    raise ValueError('expected one inspect or submit_rca call')
                original_raw = raw
                if isinstance(raw, str) and raw.strip().startswith('```json\n') and raw.strip().endswith('```'):
                    raw = raw.strip()[8:-3].strip()
                    result['normalizations'].append({'call': calls, 'operation': 'strip_whole_json_fence', 'before': original_raw, 'after': raw})
                candidate = json.loads(raw) if isinstance(raw, str) else raw
                result['answer'] = validate_answer(candidate, shown)
                attempt['kind'] = 'accepted_final'
                result['state'] = 'accepted'
                result['format_outcome'] = 'after_model_repair' if repairs else ('after_normalization' if result['normalizations'] else 'first_final_pass')
                break
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                message = str(exc)[:250]
                attempt.update(kind='invalid', validation_error=message)
                record({'type': 'validation_error', 'call': calls, 'error': message})
                if repairs >= limits['model_repairs']:
                    raise ValueError('output_invalid_after_repair:' + message)
                repairs += 1
                repairing = True
                # Explicit common repair: no retrieval and identical schema.
                errors = [{'error': message, 'instruction': 'Resubmit valid output grounded only in the unchanged evidence ledger.'}]
        if result['state'] != 'accepted':
            raise ValueError('per-run call budget exhausted')
    except (ValueError, RuntimeError) as exc:
        result['error'] = str(exc)
        result['format_outcome'] = 'terminal_invalid'
    result.update(duration_seconds=round(time.monotonic() - started, 6), calls=calls,
                  repairs=repairs, tool_calls=tool_count, shown_evidence=shown,
                  source_states={k: (next(e for e in shown if e['evidence_id'] == catalog[k]['evidence_id']).get('observation_state', catalog[k]['availability'])
                                    if k in queried else 'not_retrieved') for k in catalog})
    if result['answer']:
        by_id = citation_registry(shown)
        result['claims_trace'] = [{'claim_index': index, 'evidence': [
            {'evidence_id': eid, 'provenance_sha256': by_id[eid].get('provenance_sha256')}
            for eid in claim['evidence_ids']]} for index, claim in enumerate(result['answer']['claims'])]
    return result
