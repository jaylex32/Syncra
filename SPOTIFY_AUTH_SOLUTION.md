# Spotify Authentication - Final Solution

## Overview

**Fixed**: Spotify authentication broken by API changes on December 22, 2025
**Solution**: Hybrid authentication approach using both cookie-based TOTP tokens and OAuth Client Credentials
**Status**: ✅ Production Ready

## How It Works

### Two-Part Authentication System

Syncra uses a **hybrid authentication approach** to work around Spotify's new API restrictions:

#### 1. Cookie-Based TOTP Authentication (for playlist metadata)
- **What**: Generates temporary access tokens from your `sp_dc` cookie using TOTP (Time-based One-Time Password)
- **Used for**: Fetching playlist metadata (name, track count, track URIs)
- **Endpoint**: `https://spclient.wg.spotify.com/playlist/v2/playlist/{id}`
- **Headers Required**:
  - `Authorization: Bearer {token}` (TOTP-generated token)
  - `Client-Id: {client_id}` (extracted from TOTP token) **[CRITICAL]**
  - `Accept: application/json` (prevents protobuf response)

#### 2. OAuth Client Credentials (for track details)
- **What**: Uses OAuth 2.0 Client Credentials flow with built-in app credentials
- **Used for**: Fetching individual track information (title, artist, album)
- **Endpoint**: `https://api.spotify.com/v1/tracks/{id}` (one track at a time)
- **Why**: Spotify now requires OAuth tokens for track data retrieval (Dec 22, 2025 change)

## User Requirements

### What Users Need to Provide
- ✅ **sp_dc cookie** - User's session cookie from Spotify (obtained from browser)

### What's Built-In (No User Action Required)
- ✅ **OAuth Client ID** - Hardcoded in application
- ✅ **OAuth Client Secret** - Hardcoded in application
- ✅ **TOTP Token Generation** - Automatically generated from sp_dc cookie
- ✅ **Rate Limiting** - Built-in 100ms delay between track requests

## Technical Implementation

### Files Modified
- **main.py** - Core authentication and API interaction logic

### Key Code Locations

#### Global OAuth Configuration ([main.py:297-301](main.py#L297-L301))
```python
SP_APP_CLIENT_ID = os.getenv("SP_APP_CLIENT_ID", "880ca2262b0447bd82e4ea0b17febc16")
SP_APP_CLIENT_SECRET = os.getenv("SP_APP_CLIENT_SECRET", "c91c4b70b6e0482ebec5b91bf869c420")
SP_APP_TOKENS_FILE = os.getenv("SP_APP_TOKENS_FILE", ".spotify_oauth_cache")
```

#### Playlist Metadata Fetching ([main.py:4633-4691](main.py#L4633-L4691))
- Uses `spclient.wg.spotify.com` endpoint
- Requires `Client-Id` header (Dec 22, 2025 requirement)
- Returns track URIs, not full track details

#### Track Details Fetching ([main.py:4730-4764](main.py#L4730-L4764))
- Uses OAuth tokens via `SpotifyOAuthApp`
- Fetches tracks **one at a time** (not batched)
- 100ms delay between requests to avoid rate limiting

### Authentication Classes

#### SpotifyAnonymousAuth ([main.py:3887](main.py#L3887))
- Generates TOTP tokens from sp_dc cookie
- Manages token expiration and refresh
- Extracts client_id from token response

#### SpotifyOAuthApp ([main.py:4364](main.py#L4364))
- Manages OAuth Client Credentials flow
- Provides tokens for track API requests
- Handles token caching and renewal

## Why This Approach Works

### The Problem
On **December 22, 2025**, Spotify introduced API restrictions:
1. Regular `api.spotify.com/v1/playlists/{id}` endpoint started returning **429 rate limit errors** immediately with cookie authentication
2. Track information endpoint requires OAuth tokens (can't use cookie tokens anymore)

### The Solution
1. **Playlist Metadata**: Use Spotify's internal `spclient.wg.spotify.com` endpoint which still accepts cookie-based TOTP tokens
2. **Track Details**: Use OAuth Client Credentials for individual track requests
3. **Rate Limiting**: Fetch tracks one at a time with delays (like the reference implementation)

### Why Not Just Use OAuth?
- OAuth tokens **don't work** for algorithmic/personalized Spotify playlists (Discover Weekly, etc.)
- Cookie-based authentication is required to access user-specific playlists
- Hybrid approach gives best of both worlds

## Configuration

### app_config.json Structure
```json
{
  "sp_dc_cookie": "AQCGbtima6SToi4iexP_IG4...",
  "sp_app_client_id": "880ca2262b0447bd82e4ea0b17febc16",
  "sp_app_client_secret": "c91c4b70b6e0482ebec5b91bf869c420"
}
```

### Do Users Need to Add OAuth Credentials?
**No!** OAuth credentials are:
- ✅ Built-in as defaults in the code
- ✅ Automatically saved to `app_config.json` when user provides sp_dc cookie
- ✅ Can be overridden via environment variables if needed

Users only need to provide their **sp_dc cookie**.

## Testing

Run the authentication test script:
```bash
python test_spotify_auth.py
```

Expected output:
```
[SUCCESS] Playlist name: Trap Land
[OK] Total tracks: 100
RESULT: [SUCCESS] AUTHENTICATION WORKS!
```

## Reference Implementation

This fix is based on the approach used in: https://github.com/misiektoja/spotify_monitor

Key learnings from the reference implementation:
- Use `spclient.wg.spotify.com` for playlists with cookie auth
- Use OAuth tokens for track information
- Fetch tracks individually with delays (not batched)
- Include `Client-Id` header for cookie-based requests

## Version History

- **v2.13.0** - Initial fix attempt (failed - wrong approach)
- **v2.13.1** - Switched to spclient endpoint (partial fix)
- **v2.13.2** - Added OAuth for tracks (partial fix)
- **v2.13.3** - **FINAL WORKING SOLUTION** ✅

---

**Last Updated**: December 31, 2025
**Status**: Production Ready
**Breaking Changes**: None for end users (seamless upgrade)
