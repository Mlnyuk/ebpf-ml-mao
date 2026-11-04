#!/usr/bin/env python3
"""Build a portable offline demo from an existing embedded replay viewer."""
import argparse
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research_v4.booth import package

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT.parent/'paper-results/2026-10-29/analysis-v3/viewer/index.html')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = package(args.source, args.output)
    print(f"Offline demo: {args.output}/START.html; saved case: {data['cases'][0]['case_id']}")
