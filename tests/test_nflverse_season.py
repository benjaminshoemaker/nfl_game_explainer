from api.lib.nflverse_season import extract_game, schedule_event


def event(home_score=0, away_score=0):
    return schedule_event(dict(game_id='sample', season=2025, game_type='REG', week=1,
                               gameday='2025-09-07', gametime='13:00', home_team='BUF',
                               away_team='ARI', home_score=home_score, away_score=away_score))


def play(n, **kw):
    return dict(game_id='sample', play_id=n, season=2025, week=1, home_team='BUF',
                away_team='ARI', posteam='ARI', defteam='BUF', play_type='run',
                fixed_drive=1, drive_start_yard_line='ARI 30', yardline_100=70,
                down=1, ydstogo=10, yards_gained=0, **kw)


def changed(n, **kw):
    p = play(n)
    p.update(kw)
    return p


def team(result, name='ARI'):
    return next(t for t in result['teams'] if t['id'] == name)


def test_kickoff_return_conversion_stays_non_offensive():
    rows = [changed(1, play_type='kickoff', touchdown=1, td_team='ARI', return_touchdown=1),
            changed(2, play_type='extra_point', extra_point_attempt=1, extra_point_result='good')]
    t = team(extract_game(rows, event(away_score=7)))
    assert t['factors']['non_offensive_points']['value'] == 7
    assert t['counters']['Drives Inside 40'] == 0


def test_scramble_uses_dropback_explosive_threshold_and_app_success():
    t = team(extract_game([changed(1, yards_gained=12, qb_scramble=1)], event()))
    assert t['counters']['Explosive Plays'] == 0
    assert t['counters']['Successful Plays'] == 1


def test_return_fumble_charged_to_returning_team():
    t = team(extract_game([changed(1, play_type='punt', fumble_lost=1,
                  fumbled_1_team='BUF', fumble_recovery_1_team='ARI')], event()), 'BUF')
    assert t['counters']['Turnovers'] == 1


def test_start_uses_scrimmage_metadata_not_kickoff_metadata():
    rows = [changed(1, play_type='kickoff', drive_start_yard_line='ARI 40'), changed(2)]
    assert team(extract_game(rows, event()))['factors']['field_position']['value'] == 30


def test_conflicting_scrimmage_starts_remain_missing():
    rows = [changed(1), changed(2, drive_start_yard_line='ARI 40')]
    f = team(extract_game(rows, event()))['factors']['field_position']
    assert not f['usable'] and f['value'] is None


def test_long_touchdown_counts_trip_and_conversion():
    rows = [changed(1, yards_gained=70, touchdown=1, td_team='ARI'),
            changed(2, extra_point_attempt=1, play_type='extra_point', extra_point_result='good')]
    t = team(extract_game(rows, event(away_score=7)))
    assert t['factors']['points_per_trip']['value'] == 7
    assert t['factors']['non_offensive_points']['value'] == 0


def test_score_mismatch_withholds_scoring_factors_only():
    t = team(extract_game([changed(1)], event(away_score=7)))
    assert not t['factors']['non_offensive_points']['usable']
    assert t['factors']['success_rate']['usable']
