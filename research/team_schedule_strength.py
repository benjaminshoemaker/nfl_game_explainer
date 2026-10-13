"""Schedule difficulty from venue-adjusted scoring strength, not rating impact."""
import numpy as np
from research.team_power_baseline_audit import fit_strength


def schedule_strength(games, ids, cutoff, prior, prior_home, venues, *, exclude_focal=True):
    if any(g['week']>=cutoff for g in games):
        raise ValueError('Only earlier weeks may enter schedule strength')
    ix={t:i for i,t in enumerate(ids)}
    common,_=fit_strength(games,ids,cutoff,prior,prior_home,8,8,venues)
    out={}
    for team in ids:
        played=[g for g in games if any(t['id']==team for t in g['teams'])]
        fit_games=[g for g in games if all(t['id']!=team for t in g['teams'])] if exclude_focal else games
        strength=fit_strength(fit_games,ids,cutoff,prior,prior_home,8,8,venues)[0] if exclude_focal else common
        opponents=[]
        for g in played:
            opponent=next(t for t in g['teams'] if t['id']!=team)
            opponents.append({'gameId':g['gameId'],'week':g['week'],'id':opponent['id'],
                              'strength':float(strength[ix[opponent['id']]])})
        for o in opponents:o['contribution']=o['strength']/len(opponents)
        out[team]={'value':float(np.mean([o['strength'] for o in opponents])) if opponents else None,
                   'opponents':opponents,'games':len(opponents),'excludedFocalGames':exclude_focal}
    pool=[v['value'] for v in out.values() if v['value'] is not None]
    for row in out.values():
        row['rankPool']=len(pool)
        row['rank']=1+sum(v>row['value'] for v in pool) if row['value'] is not None else None
        row['tied']=pool.count(row['value'])>1 if row['value'] is not None else False
    return out


def prior_schedule_state(records, ids, season, venues):
    prior=None;home=2.5
    for year in sorted({g['season'] for g in records if g['season']<season}):
        games=[g for g in records if g['season']==year]
        prior,home=fit_strength(games,ids,max(g['week'] for g in games)+1,prior,home,8,8,venues)
    return prior,home
