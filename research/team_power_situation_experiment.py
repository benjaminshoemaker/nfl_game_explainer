"""Predeclare bounded situation/QB additions, then run nested selection."""
import json
from pathlib import Path
from research.build_team_seasons import save_json
from research.team_power_nested import run

ROOT=Path(__file__).resolve().parents[1]


def experiment(base):
    source=base/'model-v6-situation';meta=json.loads((source/'features.json').read_text());g=meta['groups']
    old=json.loads((base/'model-v3/protocol.json').read_text())
    margin=[s for s in old['marginCandidates'] if s['family'] in ('point_baseline','point_context')]
    prob=[s for s in old['probabilityCandidates'] if s['family'] in ('point_baseline','point_context')]
    core=g['original_p8_h8']+g['context']
    sets={'core':core,'early_downs':core+g['early'],'close_state':core+g['close'],
          'close_pass_rush':core+g['close_pass']+g['close_rush'],
          'qb_history':core+g['qb_history'],
          'situations_and_qb':core+g['early']+g['close_pass']+g['close_rush']+g['qb_history']}
    for family,columns in sets.items():
        for a in (10,100,1000):margin.append({'family':family,'columns':columns,'kind':'ridge','strength':a})
        for a in (.1,1):margin.append({'family':family+'_elastic','columns':columns,'kind':'elastic','strength':a})
        for c in (.001,.01,.1):prob.append({'family':family,'columns':columns,'kind':'ridge','strength':c})
    for leaves in (3,7):
        spec={'family':'situation_nonlinear','columns':sets['situations_and_qb'],'kind':'tree','strength':leaves}
        margin.append(spec);prob.append(spec)
    save_json(source/'protocol.json',{'marginCandidates':margin,'probabilityCandidates':prob,
        'warning':'Candidate design is retrospective. No next-start labels or future-week outcomes.',
        'newInputs':['early down efficiency','close-score first-three-quarter efficiency','past QB usage']})
    run(source,source/'nested')


if __name__=='__main__':experiment(ROOT/'game_summaries/nflverse')
