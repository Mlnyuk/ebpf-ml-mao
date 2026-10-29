#!/usr/bin/env python3
"""Descriptive plots from preserved CSVs; no quality grading or model calls."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def rows(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def save(fig, out, name):
    fig.savefig(out / (name + '.svg'), bbox_inches='tight')
    fig.savefig(out / (name + '.pdf'), bbox_inches='tight')
    plt.close(fig)


def plot(old, new, out):
    out.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({'font.size': 9, 'svg.fonttype': 'none'})
    for group in ('primary', 'ablation'):
        data = [r for r in rows(old/'methods.csv') if r['view']=='original' and r['group']==group]
        fig, axes = plt.subplots(1, 3, figsize=(13, 4))
        labels = [r['arm'].replace('selective-ebpf-', '').replace('selective-', 'sel-') for r in data]
        for ax, key, label in zip(axes, ('mean_tokens', 'known_cost_usd', 'mean_seconds'),
                                  ('Mean investigation tokens', 'Mean investigation cost (USD)', 'Mean investigation time (s)')):
            values=[float(r[key])/(int(r['investigations']) if key=='known_cost_usd' else 1) for r in data]
            ax.barh(labels, values, color='#426c91')
            ax.set_xlabel(label); ax.invert_yaxis(); ax.grid(axis='x', alpha=.2)
        fig.suptitle('paper-clock-v3: '+group+' / original occurrences only')
        fig.text(.01, -.05, '6 captured occurrences; 2 LLM repeats per method. Failures included. Human diagnostic quality: NOT EVALUATED.')
        fig.tight_layout(); save(fig,out,'clock-v3-'+group)
    data=[r for r in rows(new/'methods.csv') if r['view']=='original']
    breadths=sorted({r['breadth'] for r in data})
    fig, axes=plt.subplots(1,3,figsize=(12,4))
    for ax,key,label in zip(axes,('mean_tokens','known_cost_usd','mean_seconds'),
                            ('Mean investigation tokens','Mean investigation cost (USD)','Mean investigation time (s)')):
        for i,arm in enumerate(('batch','selective')):
            chosen=[next(r for r in data if r['breadth']==b and r['arm']==arm) for b in breadths]
            values=[float(r[key])/(int(r['investigations']) if key=='known_cost_usd' else 1) for r in chosen]
            ax.bar([j+(i-.5)*.36 for j in range(len(breadths))],values,width=.36,label=arm)
        ax.set_xticks(range(len(breadths)),breadths);ax.set_ylabel(label);ax.legend();ax.grid(axis='y',alpha=.2)
    fig.suptitle('paper-next-v1: paired evidence breadth / descriptive usage')
    fig.text(.01,-.05,'20 fresh occurrences; paired breadth variants are dependent. One LLM run per cell. Failures included; quality NOT EVALUATED.')
    fig.tight_layout();save(fig,out,'next-v1-breadth')
    pairs=[r for r in rows(new/'paired-deltas.csv') if r['view']=='original']
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,key,label in zip(axes,('delta_tokens_selective_minus_batch','delta_cost_selective_minus_batch'),
                            ('Selective minus batch: tokens','Selective minus batch: USD')):
        for j,b in enumerate(breadths):
            chosen=sorted([r for r in pairs if r['breadth']==b],key=lambda r:r['parent'])
            ax.scatter([j+(i-(len(chosen)-1)/2)*.012 for i in range(len(chosen))],
                       [float(r[key]) for r in chosen],alpha=.7,s=22)
        ax.axhline(0,color='black',linewidth=.8);ax.set_xticks(range(len(breadths)),breadths)
        ax.set_ylabel(label);ax.grid(axis='y',alpha=.2)
    fig.suptitle('Per-occurrence paired differences (negative = lower selective usage)')
    fig.text(.01,-.04,'Each dot is one captured occurrence. No accuracy inference, confidence intervals, or independent-cluster claim.')
    fig.tight_layout();save(fig,out,'next-v1-paired-differences')
    (out/'plot-metadata.json').write_text(json.dumps({'matplotlib':matplotlib.__version__,
        'inputs':[str(old/'methods.csv'),str(new/'methods.csv'),str(new/'paired-deltas.csv')],
        'scope':'Posthoc descriptive visualization; original observations only. No human grading or inferential significance.',
        'units':'Cost is returned provider USD usage, not a hypothetical list-price estimate.'},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('old','new','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();plot(a.old,a.new,a.output)
