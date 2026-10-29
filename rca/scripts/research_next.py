#!/usr/bin/env python3
"""Explicit next-version research entrypoint; default actions never call an LLM."""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['analyze','freeze','capture','run','report','viewer','serve','pipeline'])
    p.add_argument('--source',type=Path,default=ROOT/'artifacts/paper-clock-v3-20261029')
    p.add_argument('--output',type=Path,default=ROOT/'artifacts/paper-clock-v3-analysis-v1')
    p.add_argument('--study',type=Path,default=ROOT/'artifacts/paper-next-v1-20261029')
    p.add_argument('--cluster-key',action='store_true');p.add_argument('--key-file',type=Path)
    p.add_argument('--enable-live',action='store_true');p.add_argument('--port',type=int,default=8765)
    a=p.parse_args()
    if a.action=='analyze':
        from research_v4.analyze import analyze
        result=analyze(a.source.resolve(),a.output.resolve())
        print(json.dumps({k:v for k,v in result.items() if k!='methods'},ensure_ascii=False))
    elif a.action=='freeze':
        from research_v4.protocol import freeze
        freeze(a.study.resolve());print('Protocol and implementation frozen before evaluation capture.')
    elif a.action=='capture':
        from research_v4.capture import capture
        capture(a.study.resolve())
    elif a.action=='run':
        if not(a.cluster_key or a.key_file):p.error('explicit key source required')
        from research_v4.run import execute
        execute(a.study.resolve(),a)
    elif a.action=='report':
        from research_v4.report import report
        print(json.dumps(report(a.study.resolve()),ensure_ascii=False))
    elif a.action=='viewer':
        from research_v4.viewer import build
        build(a.source.resolve(),a.output.resolve())
    elif a.action=='serve':
        from research_v4.viewer import serve
        serve(a.source.resolve(),a.output.resolve(),a)
    elif a.action=='pipeline':
        if not(a.cluster_key or a.key_file):p.error('explicit key source required')
        from research_v4.capture import capture
        from research_v4.run import execute
        from research_v4.report import report
        from research_v4.viewer import build
        study=a.study.resolve();capture(study);execute(study,a)
        summary=report(study);build(study,study/'viewer')
        print(json.dumps({'pipeline_finished':True,'recorded_runs':summary['runs'],'human_quality':'NOT_EVALUATED_BY_HUMANS','online_overhead':'NOT_MEASURED'},ensure_ascii=False))

if __name__=='__main__':main()
