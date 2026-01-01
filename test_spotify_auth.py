#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Spotify authentication to verify sp_dc cookie and TOTP auth work
"""
import sys
import json
import os

# Fix Windows console encoding
if os.name == 'nt':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

from main import SpotifyAnonymousAuth, SpotifyOAuthApp

def test_auth():
    print("=" * 60)
    print("SPOTIFY AUTHENTICATION TEST")
    print("=" * 60)

    # Load config to get sp_dc cookie
    try:
        with open('app_config.json', 'r') as f:
            config = json.load(f)
            sp_dc = config.get('sp_dc_cookie', '')
            print(f"\n[OK] Loaded sp_dc cookie: {sp_dc[:30]}...{sp_dc[-10:]}")
    except Exception as e:
        print(f"\n[ERROR] Failed to load config: {e}")
        return False

    # Set global variable
    import main
    main.SP_DC_COOKIE = sp_dc

    # Test TOTP authentication
    print("\n" + "-" * 60)
    print("Testing TOTP Authentication...")
    print("-" * 60)

    try:
        auth = SpotifyAnonymousAuth()
        print("[OK] SpotifyAnonymousAuth initialized")

        print("\nAttempting to get access token...")
        token = auth.get_token()

        if token and len(token) > 50:
            print(f"[SUCCESS] Token obtained: {token[:30]}...{token[-10:]}")
            print(f"[OK] Token length: {len(token)} characters")
            print(f"[OK] Token valid: {auth.is_token_valid()}")

            # Test with actual playlist using cookie token + Client-Id
            print("\n" + "-" * 60)
            print("Testing Playlist Access with Cookie Token...")
            print("-" * 60)

            import requests
            client_id = auth.cached_client_id
            headers = {
                'Authorization': f'Bearer {token}',
                'Client-Id': client_id,  # CRITICAL: Required for cookie-based tokens
                'User-Agent': auth.user_agent,
                'Accept': 'application/json',  # Request JSON instead of protobuf
            }

            print(f"Using Client-Id: {client_id}")

            playlist_id = '37i9dQZF1DXde9tuMHuIsj'
            url = f'https://spclient.wg.spotify.com/playlist/v2/playlist/{playlist_id}'

            print(f"Requesting: {url}")
            response = requests.get(url, headers=headers, timeout=30)

            print(f"Response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                # spclient endpoint returns different structure
                playlist_name = data.get('attributes', {}).get('name', 'Unknown')
                total_tracks = data.get('length', 0)
                print(f"\n[SUCCESS!!!] Playlist name: {playlist_name}")
                print(f"[OK] Total tracks: {total_tracks}")
                return True
            elif response.status_code == 429:
                print(f"\n[RATE LIMITED] - Wait a few minutes and try again")
                print(f"  Retry-After: {response.headers.get('Retry-After', 'Not specified')} seconds")
                return False
            else:
                print(f"\n[ERROR] {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return False

        else:
            print(f"[ERROR] Token appears invalid: {token}")
            return False

    except Exception as e:
        print(f"\n[FAILED] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\nThis script tests if your Spotify authentication is working.\n")
    success = test_auth()

    print("\n" + "=" * 60)
    if success:
        print("RESULT: [SUCCESS] AUTHENTICATION WORKS!")
        print("\nYour Spotify authentication is configured correctly.")
        print("If the app still fails, the issue is elsewhere.")
    else:
        print("RESULT: [FAILED] AUTHENTICATION FAILED")
        print("\nPossible issues:")
        print("1. sp_dc cookie is expired - Get a fresh one from Spotify")
        print("2. Temporary rate limiting - Wait 5-10 minutes")
        print("3. Network/firewall issue")
    print("=" * 60)

    sys.exit(0 if success else 1)
