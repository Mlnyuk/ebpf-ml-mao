"""Deterministic evidence encoding, not diagnosis or anomaly detection.

Log templates retain every numeric string (including timestamps), in order.
Metric columns retain every original timestamp and value. No min/max-only
sampling, semantic log filtering, or LLM summarization is performed here.
"""
import copy
import re

from .common import compact


NUMBER = re.compile(r'(-?\d+(?:\.\d+)?)')
ENCODING = 'numeric-template-columns-v1'
INDEXED_ENCODING = 'indexed-template-columns-v2'


def pack_logs(lines):
    blocks = []
    index = 0
    while index < len(lines):
        parts = NUMBER.split(lines[index])
        template = parts[::2]
        rows = [parts[1::2]]
        end = index + 1
        while end < len(lines):
            other = NUMBER.split(lines[end])
            if other[::2] != template:
                break
            rows.append(other[1::2])
            end += 1
        columns = []
        for col in zip(*rows):
            columns.append(col[0] if len(set(col)) == 1 else list(col))
        block = {'template': template, 'columns': columns, 'count': len(rows)}
        if len(compact(block)) < len(compact(lines[index:end])):
            blocks.append(block)
        else:
            blocks.extend(lines[index:end])
        index = end
    packed = {'encoding': ENCODING, 'blocks': blocks}
    return packed if len(compact(packed)) < len(compact(lines)) else lines


def unpack_logs(packed):
    if isinstance(packed, list):
        return list(packed)
    if packed.get('encoding') == INDEXED_ENCODING:
        offsets = [0] * len(packed['templates'])
        lines = []
        for index in packed['order']:
            block = packed['templates'][index]
            row = offsets[index]
            offsets[index] += 1
            line = block['template'][0]
            for col, column in enumerate(block['columns']):
                line += (column[row] if isinstance(column, list) else column) + block['template'][col + 1]
            lines.append(line)
        return lines
    if packed.get('encoding') != ENCODING:
        raise ValueError('unknown log encoding')
    lines = []
    for block in packed['blocks']:
        if isinstance(block, str):
            lines.append(block)
            continue
        for row in range(block['count']):
            line = block['template'][0]
            for index, column in enumerate(block['columns']):
                line += (column[row] if isinstance(column, list) else column) + block['template'][index + 1]
            lines.append(line)
    return lines


def pack_logs_indexed(lines):
    """Group interleaved formats while preserving every string and its order.

    No semantic filtering or timestamp arithmetic. Column strings retain zeros,
    precision, signs and numeric identifiers. Keep v1/raw if either is smaller.
    """
    groups, lookup, order = [], {}, []
    for line in lines:
        parts = NUMBER.split(line)
        key = tuple(parts[::2])
        if key not in lookup:
            lookup[key] = len(groups)
            groups.append({'template': list(key), 'rows': []})
        index = lookup[key]
        groups[index]['rows'].append(parts[1::2])
        order.append(index)
    templates = [{'template': group['template'], 'columns': [
        col[0] if len(set(col)) == 1 else list(col) for col in zip(*group['rows'])]}
        for group in groups]
    packed = {'encoding': INDEXED_ENCODING, 'order': order, 'templates': templates}
    return min((pack_logs(lines), packed), key=lambda value: len(compact(value)))


def pack_series(series):
    # Only column-pack series sharing exactly the same time axis. Otherwise
    # leave the representation untouched; never invent, round, or fill samples.
    if not series or any('points' not in item for item in series.values()):
        return series
    axis = [p[0] for p in next(iter(series.values()))['points']]
    if any([p[0] for p in item['points']] != axis for item in series.values()):
        return series
    packed = {'encoding': 'shared-time-axis-v1', 'timestamps': axis, 'series': {
        name: {**{k: v for k, v in item.items() if k != 'points'},
               'values': [p[1] for p in item['points']]}
        for name, item in series.items()}}
    return packed if len(compact(packed)) < len(compact(series)) else series


def unpack_series(packed):
    if packed.get('encoding') != 'shared-time-axis-v1':
        return copy.deepcopy(packed)
    return {name: {**{k: v for k, v in item.items() if k != 'values'},
                   'points': [list(p) for p in zip(packed['timestamps'], item['values'])]}
            for name, item in packed['series'].items()}


def present_evidence(evidence, incident, mode='compact'):
    if mode not in ('full', 'compact', 'full-v4', 'compact-v4'):
        raise ValueError('unsupported evidence mode')
    result = copy.deepcopy(evidence)
    if mode in ('full', 'full-v4'):
        return result
    target = result.get('target')
    # Substitute only proven-equal scope fields; mismatches remain visible.
    if target and all(k in incident and incident[k] == v for k, v in target.items()):
        result['target'] = {'ref': 'incident', 'fields': list(target)}
    if 'lines' in result:
        result['lines'] = pack_logs_indexed(result['lines']) if mode == 'compact-v4' else pack_logs(result['lines'])
    if 'series' in result:
        result['series'] = pack_series(result['series'])
    # Encoding overhead must never enlarge the evidence payload.
    return result if len(compact(result)) < len(compact(evidence)) else copy.deepcopy(evidence)


def restore_evidence(evidence, incident):
    result = copy.deepcopy(evidence)
    target = result.get('target', {})
    if target.get('ref') == 'incident' and set(target) == {'ref', 'fields'}:
        result['target'] = {key: incident[key] for key in target['fields']}
    if 'lines' in result:
        result['lines'] = unpack_logs(result['lines'])
    if 'series' in result:
        result['series'] = unpack_series(result['series'])
    return result


def ledger_messages(system, incident, evidence, errors, remaining_tools):
    # Start a fresh stateless request: no dangling assistant/tool call IDs.
    # Every evidence item previously shown remains available, once per ID.
    unique = {item['evidence_id']: item for item in evidence}
    ledger = {'incident': incident, 'evidence': list(unique.values()),
              'tool_errors': errors, 'remaining_tool_calls': remaining_tools}
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': compact(ledger)}]
