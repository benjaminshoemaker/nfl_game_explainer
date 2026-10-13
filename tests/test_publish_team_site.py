import json
from pathlib import Path
import pytest
from research.publish_team_site import export
from research.render_team_prototype import public_payload
from research.weekly_team_ratings import write_new, seal


def fixture_archive(tmp_path):
    source=tmp_path/'source'; run=source/'weekly-archive/run1'
    manifest={'season':2026,'throughWeek':5,'archive':'weekly-archive/run1',
              'publishedAt':'2026-10-13T06:00:00+00:00',
              'inputs':[{'path':'/Users/operator/sources/file.parquet','sha256':'sourcehash'}]}
    write_new(run/'manifest.json',manifest)
    write_new(run/'predictions.json',{'modelSha256':'modelhash','games':[]})
    write_new(run/'sources/private.json',{'internal':'not public'})
    seal(run);write_new(source/'weekly-latest.json',manifest)
    return source,run


def fake_render(source,output,**kwargs):
    assert kwargs['public_mode']
    output.write_text('<html>review</html>')


def test_public_export_is_whitelisted_and_preserves_forecasts(tmp_path,monkeypatch):
    source,run=fixture_archive(tmp_path)
    monkeypatch.setattr('research.publish_team_site.render',fake_render)
    output=tmp_path/'public';export(source,output)
    published=output/'team-data/run1'
    assert (published/'predictions.json').read_bytes()==(run/'predictions.json').read_bytes()
    assert not (published/'sources').exists()
    assert '/Users/' not in (published/'manifest.json').read_text()
    assert json.loads((published/'manifest.json').read_text())['inputs'][0]['path']=='file.parquet'
    export(source,output)  # identical publication is safe to repeat
    (published/'predictions.json').write_text('{}')
    with pytest.raises(ValueError,match='replace published archive'):
        export(source,output)


def test_export_rejects_changed_source(tmp_path,monkeypatch):
    source,run=fixture_archive(tmp_path)
    monkeypatch.setattr('research.publish_team_site.render',fake_render)
    (run/'predictions.json').write_text('{}')
    with pytest.raises(ValueError,match='Archive changed'):
        export(source,tmp_path/'public')


def test_public_provenance_keeps_urls_and_checksums():
    assert public_payload({'path':'/tmp/source.csv','url':'https://example.com/source.csv','hash':'abc'}) == {
        'path':'source.csv','url':'https://example.com/source.csv','hash':'abc'}
