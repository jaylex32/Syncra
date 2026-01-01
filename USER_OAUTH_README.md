# Using Your Own Spotify OAuth Credentials

## TL;DR

**Having rate limit issues?** Create your own Spotify OAuth app (takes 5 minutes, totally free):

1. Visit: https://developer.spotify.com/dashboard
2. Create app with redirect URI: `http://localhost:8888/callback`
3. Copy Client ID + Secret
4. Add to `app_config.json`:
   ```json
   {
     "sp_dc_cookie": "your_cookie",
     "sp_app_client_id": "your_client_id",
     "sp_app_client_secret": "your_client_secret"
   }
   ```
5. Restart Syncra

**Full guide:** [SPOTIFY_OAUTH_SETUP_GUIDE.md](SPOTIFY_OAUTH_SETUP_GUIDE.md)

---

## Why Use Your Own Credentials?

### Default (Shared Credentials)
- ✅ **Works out of the box** - no setup required
- ✅ **Good for personal use** - 1-5 users
- ⚠️ **May hit rate limits** with heavy usage
- ⚠️ **Shared quota** with all Syncra users

### Your Own Credentials
- ✅ **Your own rate limit quota** (~180 requests/minute)
- ✅ **No sharing** - guaranteed performance
- ✅ **Unlimited playlists** - no bottlenecks
- ✅ **100% free** - Spotify Developer is free
- ⏱️ **5 minute setup** - one-time configuration

---

## Configuration Template

### Minimal (Works Out of Box)
```json
{
  "sp_dc_cookie": "AQCGbtima6SToi4iexP..."
}
```
Uses default shared OAuth credentials.

### Recommended (Your Own OAuth)
```json
{
  "sp_dc_cookie": "AQCGbtima6SToi4iexP...",
  "sp_app_client_id": "880ca2262b0447bd82e4ea0b17febc16",
  "sp_app_client_secret": "c91c4b70b6e0482ebec5b91bf869c420"
}
```
Uses your personal OAuth credentials.

### Full Template
See: [app_config.json.template](app_config.json.template)

---

## How to Get Credentials

### Step 1: Spotify Developer Dashboard
![Spotify Dashboard](https://developer.spotify.com/images/guidelines/design/icon1@2x.png)

1. Go to https://developer.spotify.com/dashboard
2. Log in with your Spotify account (free or premium)
3. Click **"Create app"**

### Step 2: Fill App Details

```
App name:        Syncra Personal
App description: Personal music playlist sync tool
Redirect URI:    http://localhost:8888/callback
```

✓ Check: "I understand and agree with Spotify's Developer Terms of Service"

Click **"Save"**

### Step 3: Get Credentials

1. Click on your app name
2. Click **"Settings"** (top right)
3. You'll see:
   - **Client ID** - Copy this
   - **Client Secret** - Click "View client secret", then copy

### Step 4: Add to Syncra

Edit `app_config.json`:

```json
{
  "sp_dc_cookie": "YOUR_COOKIE_FROM_BROWSER",
  "sp_app_client_id": "PASTE_CLIENT_ID_HERE",
  "sp_app_client_secret": "PASTE_CLIENT_SECRET_HERE"
}
```

### Step 5: Verify It Works

```bash
python test_spotify_auth.py
```

Expected output:
```
[SUCCESS] Token obtained: BQB5j7...
[SUCCESS!!!] Playlist name: Trap Land
RESULT: [SUCCESS] AUTHENTICATION WORKS!
```

---

## Environment Variables (Alternative)

Instead of `app_config.json`, you can use environment variables:

### Windows
```cmd
set SP_APP_CLIENT_ID=your_client_id
set SP_APP_CLIENT_SECRET=your_client_secret
```

### Linux/Mac
```bash
export SP_APP_CLIENT_ID=your_client_id
export SP_APP_CLIENT_SECRET=your_client_secret
```

Priority: Environment Variables > app_config.json > Built-in Defaults

---

## When Should You Create Your Own?

### ✅ You Should Create Your Own If:
- You're getting "429 Rate Limited" errors
- You sync large playlists (100+ tracks) frequently
- You run automated/scheduled syncs
- You want guaranteed performance
- You use Syncra daily

### ⏸️ You Can Skip This If:
- Syncra works fine for you currently
- You only sync occasionally (weekly/monthly)
- You work with small playlists (< 50 tracks)
- You're just testing Syncra

---

## Troubleshooting

### Problem: "Invalid client" error
**Cause:** Wrong Client ID or Secret

**Fix:**
1. Go back to Spotify Dashboard → Settings
2. Re-copy credentials (ensure no extra spaces)
3. Update `app_config.json`
4. Restart Syncra

### Problem: Still using default credentials
**Cause:** Cache file not updated

**Fix:**
1. Delete `.spotify_oauth_cache`
2. Restart Syncra
3. New cache will use YOUR credentials

### Problem: "Redirect URI mismatch"
**Cause:** Forgot to add redirect URI

**Fix:**
1. Spotify Dashboard → Your App → Settings
2. Under "Redirect URIs" add: `http://localhost:8888/callback`
3. Click "Add" then "Save"

---

## Security

### ⚠️ Keep Your Client Secret Private!

**DO NOT:**
- ❌ Share on public forums/Discord/Reddit
- ❌ Commit to GitHub (if your repo is public)
- ❌ Post screenshots showing the secret
- ❌ Share with strangers

**DO:**
- ✅ Keep in local `app_config.json`
- ✅ Use environment variables for extra security
- ✅ Rotate secret if exposed (Spotify Dashboard → Rotate)

### If Your Secret Leaks:

1. Go to Spotify Dashboard
2. Click your app → Settings
3. Click **"Rotate client secret"**
4. Update `app_config.json` with new secret

---

## FAQ

**Q: Is this free?**
A: Yes! Spotify Developer accounts are 100% free.

**Q: Will this affect my Spotify listening?**
A: No, this is completely separate from your music listening.

**Q: Can I use the same OAuth app on multiple computers?**
A: Yes! Just copy `app_config.json` to each computer.

**Q: What if I have a Spotify Free account?**
A: Perfectly fine! OAuth works with both Free and Premium.

**Q: Can I share my OAuth credentials with friends?**
A: You can, but you'll share rate limits. Better for everyone to make their own.

**Q: How long do credentials last?**
A: Forever! Unless you manually rotate/delete them.

**Q: Do I need to renew annually?**
A: No, credentials are permanent.

---

## Need Help?

**Quick Setup:** [SPOTIFY_QUICK_SETUP.txt](SPOTIFY_QUICK_SETUP.txt)
**Detailed Guide:** [SPOTIFY_OAUTH_SETUP_GUIDE.md](SPOTIFY_OAUTH_SETUP_GUIDE.md)
**Technical Details:** [SPOTIFY_AUTH_SOLUTION.md](SPOTIFY_AUTH_SOLUTION.md)

**Test Authentication:**
```bash
python test_spotify_auth.py
```

---

**Created:** December 31, 2025
**Difficulty:** Easy (5-10 minutes)
**Cost:** Free
**Recommended:** Yes (if you use Syncra regularly)
