"""
Diagnostic script to inspect ESPN's summary endpoint and find pre-game WP.
Run with: python debug_pregame_wp.py <game_id>

Example game IDs to try:
  401671790  (2024 season game)
  401547417  (2023 season game)
"""
import sys
import json
import requests


def debug_summary_endpoint(game_id: str):
    """Fetch and dump the summary endpoint to find where pregame WP lives."""
    
    url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"Fetching: {url}\n")
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"ERROR fetching data: {e}")
        return
    
    # Save full response for inspection
    with open(f"debug_summary_{game_id}.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Full response saved to: debug_summary_{game_id}.json\n")
    
    # List top-level keys
    print("=" * 60)
    print("TOP-LEVEL KEYS IN RESPONSE:")
    print("=" * 60)
    for key in data.keys():
        val = data[key]
        if isinstance(val, dict):
            print(f"  {key}: dict with {len(val)} keys -> {list(val.keys())[:5]}...")
        elif isinstance(val, list):
            print(f"  {key}: list with {len(val)} items")
        else:
            print(f"  {key}: {type(val).__name__} = {str(val)[:50]}")
    
    # Check for predictor
    print("\n" + "=" * 60)
    print("LOOKING FOR PREDICTOR DATA:")
    print("=" * 60)
    
    if 'predictor' in data:
        print("\n✓ Found 'predictor' key!")
        print(json.dumps(data['predictor'], indent=2))
    else:
        print("\n✗ No 'predictor' key found at top level")
        
        # Search recursively for anything with "projection" or "predictor"
        print("\nSearching for projection/predictor fields...")
        found = search_for_keys(data, ['predictor', 'projection', 'gameProjection', 'winProbability'])
        if found:
            for path, value in found:
                print(f"\n  Found at path: {path}")
                print(f"  Value: {json.dumps(value, indent=4)[:500]}")
    
    # Check for winprobability array (alternative source)
    print("\n" + "=" * 60)
    print("LOOKING FOR WIN PROBABILITY ARRAY:")
    print("=" * 60)
    
    if 'winprobability' in data:
        wp = data['winprobability']
        print(f"\n✓ Found 'winprobability' with {len(wp)} entries")
        if wp:
            print("\nFirst entry (should be pregame or first play):")
            print(json.dumps(wp[0], indent=2))
            if len(wp) > 1:
                print("\nSecond entry:")
                print(json.dumps(wp[1], indent=2))
    else:
        print("\n✗ No 'winprobability' key found")
    
    # Check pickcenter for odds-based probability
    print("\n" + "=" * 60)
    print("LOOKING FOR PICKCENTER (ODDS) DATA:")
    print("=" * 60)
    
    if 'pickcenter' in data:
        print("\n✓ Found 'pickcenter':")
        print(json.dumps(data['pickcenter'], indent=2)[:1000])
    else:
        print("\n✗ No 'pickcenter' key found")
    
    # Check header/competitions for any WP info
    print("\n" + "=" * 60)
    print("CHECKING HEADER/COMPETITIONS:")
    print("=" * 60)
    
    header = data.get('header', {})
    competitions = header.get('competitions', [])
    if competitions:
        comp = competitions[0]
        print(f"\nCompetition keys: {list(comp.keys())}")
        
        # Check competitors for any probability field
        for competitor in comp.get('competitors', []):
            team = competitor.get('team', {}).get('abbreviation', '?')
            home_away = competitor.get('homeAway', '?')
            print(f"\n{team} ({home_away}):")
            # Look for any probability-related fields
            for key in competitor.keys():
                if 'prob' in key.lower() or 'win' in key.lower() or 'project' in key.lower():
                    print(f"  {key}: {competitor[key]}")


def search_for_keys(obj, target_keys, path="root"):
    """Recursively search for keys containing any of the target strings."""
    found = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_lower = key.lower()
            if any(t.lower() in key_lower for t in target_keys):
                found.append((f"{path}.{key}", value))
            found.extend(search_for_keys(value, target_keys, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:3]):  # Only check first 3 items
            found.extend(search_for_keys(item, target_keys, f"{path}[{i}]"))
    
    return found


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_pregame_wp.py <game_id>")
        print("\nExample game IDs:")
        print("  401671790  (2024 season)")
        print("  401547417  (2023 season)")
        sys.exit(1)
    
    game_id = sys.argv[1]
    debug_summary_endpoint(game_id)