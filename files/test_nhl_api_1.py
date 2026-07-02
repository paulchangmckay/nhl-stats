#!/usr/bin/env python3
"""
NHL API Test Script
Tests connectivity and examines data structure from the Unofficial NHL API
"""

import requests
import json

def test_teams_endpoint():
    """Test the teams endpoint and display sample data"""
    print("=" * 60)
    print("Testing: GET /api/v1/teams")
    print("=" * 60)
    
    url = "https://statsapi.web.nhl.com/api/v1/teams"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise error for bad status codes
        
        data = response.json()
        
        print(f"✓ Status Code: {response.status_code}")
        print(f"✓ Number of teams: {len(data.get('teams', []))}")
        print("\nSample team data (first team):")
        print("-" * 60)
        
        if data.get('teams'):
            first_team = data['teams'][0]
            print(json.dumps(first_team, indent=2))
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        return False

def test_schedule_endpoint():
    """Test the schedule endpoint for current season"""
    print("\n" + "=" * 60)
    print("Testing: GET /api/v1/schedule (current season)")
    print("=" * 60)
    
    # NHL season format: 20242025 for 2024-25 season
    url = "https://statsapi.web.nhl.com/api/v1/schedule?season=20242025"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"✓ Status Code: {response.status_code}")
        print(f"✓ Total dates with games: {data.get('totalGames', 'N/A')}")
        
        # Show a sample game
        if data.get('dates') and len(data['dates']) > 0:
            first_date = data['dates'][0]
            print(f"\nSample game date: {first_date.get('date')}")
            
            if first_date.get('games') and len(first_date['games']) > 0:
                sample_game = first_date['games'][0]
                home_team = sample_game.get('teams', {}).get('home', {}).get('team', {}).get('name', 'Unknown')
                away_team = sample_game.get('teams', {}).get('away', {}).get('team', {}).get('name', 'Unknown')
                
                print(f"Sample game: {away_team} @ {home_team}")
                print(f"Game ID: {sample_game.get('gamePk')}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        return False

def test_specific_team():
    """Test getting data for a specific team (Toronto Maple Leafs)"""
    print("\n" + "=" * 60)
    print("Testing: GET /api/v1/teams/10 (Toronto Maple Leafs)")
    print("=" * 60)
    
    url = "https://statsapi.web.nhl.com/api/v1/teams/10"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('teams') and len(data['teams']) > 0:
            team = data['teams'][0]
            print(f"✓ Status Code: {response.status_code}")
            print(f"✓ Team Name: {team.get('name')}")
            print(f"✓ Abbreviation: {team.get('abbreviation')}")
            print(f"✓ Division: {team.get('division', {}).get('name')}")
            print(f"✓ Conference: {team.get('conference', {}).get('name')}")
            print(f"✓ Venue: {team.get('venue', {}).get('name')}")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("\n🏒 NHL API CONNECTIVITY TEST 🏒\n")
    
    # Run all tests
    tests = [
        test_teams_endpoint,
        test_schedule_endpoint,
        test_specific_team
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! API is working correctly.")
        print("\n📝 Next steps:")
        print("   1. Explore the API responses in detail")
        print("   2. Design database schema to match data structure")
        print("   3. Build data ingestion scripts")
    else:
        print("✗ Some tests failed. Check your internet connection or API status.")

if __name__ == "__main__":
    main()
