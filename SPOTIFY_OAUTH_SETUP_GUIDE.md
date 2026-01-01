# Spotify OAuth App Setup Guide

## Why Create Your Own OAuth App?

If you're experiencing **rate limit errors** or want **unlimited API access**, you can create your own Spotify OAuth application. This gives you:

- ✅ **Your own rate limit quota** (~180 requests/minute)
- ✅ **No sharing with other users**
- ✅ **More reliable performance**
- ✅ **100% free** (Spotify Developer account is free)

## Step-by-Step Setup

### Step 1: Create a Spotify Developer Account

1. Go to **https://developer.spotify.com/dashboard**
2. Click **"Log In"** (use your regular Spotify account)
3. Accept the **Terms of Service** if prompted

### Step 2: Create a New App

1. Click **"Create app"** button
2. Fill in the app details:

   ```
   App name: Syncra Personal (or any name you want)
   App description: Personal playlist sync tool
   Redirect URI: http://localhost:8888/callback
   ```

3. Check the box: **"I understand and agree with Spotify's Developer Terms of Service and Design Guidelines"**
4. Click **"Save"**

### Step 3: Get Your Credentials

1. Click on your newly created app
2. Click **"Settings"** button (top right)
3. You'll see:
   - **Client ID** (a long string like: `880ca2262b0447bd82e4ea0b17febc16`)
   - **Client Secret** (click "View client secret" to reveal)

4. **Copy both values** - you'll need them in the next step

### Step 4: Configure Syncra

Open your `app_config.json` file and add your credentials:

```json
{
  "sp_dc_cookie": "YOUR_SP_DC_COOKIE_HERE",
  "sp_app_client_id": "YOUR_CLIENT_ID_HERE",
  "sp_app_client_secret": "YOUR_CLIENT_SECRET_HERE"
}
```

**Example:**
```json
{
  "sp_dc_cookie": "AQCGbtima6SToi4iexP_IG4_b1vgry...",
  "sp_app_client_id": "880ca2262b0447bd82e4ea0b17febc16",
  "sp_app_client_secret": "c91c4b70b6e0482ebec5b91bf869c420"
}
```

### Step 5: Restart Syncra

Close and reopen Syncra. It will now use **your personal OAuth credentials** instead of the shared ones.

## Visual Guide

### What the Spotify Dashboard Looks Like

```
┌─────────────────────────────────────────────────────┐
│  Spotify for Developers                             │
├─────────────────────────────────────────────────────┤
│                                                      │
│  My Apps                        [Create app]        │
│                                                      │
│  ┌────────────────────────────┐                     │
│  │  Syncra Personal           │                     │
│  │  Personal playlist sync    │    [Settings]       │
│  │  Client ID: 880ca22...     │                     │
│  └────────────────────────────┘                     │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### Settings Page

```
┌─────────────────────────────────────────────────────┐
│  App Settings - Syncra Personal                     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  Basic Information                                   │
│  ─────────────────                                   │
│  Client ID:                                          │
│  880ca2262b0447bd82e4ea0b17febc16                   │
│                                                      │
│  Client Secret:                [View client secret] │
│  c91c4b70b6e0482ebec5b91bf869c420                   │
│                                                      │
│  Redirect URIs:                                      │
│  http://localhost:8888/callback                      │
│                                                      │
└─────────────────────────────────────────────────────┘
```

## Verification

After configuring your credentials, you can verify they work:

### Method 1: Run Test Script

```bash
python test_spotify_auth.py
```

You should see:
```
[SUCCESS] Token obtained: BQB5j7...
[OK] Token length: 251 characters
[SUCCESS!!!] Playlist name: Trap Land
RESULT: [SUCCESS] AUTHENTICATION WORKS!
```

### Method 2: Check Logs

When Syncra starts, look for this log message:
```
✅ Spotify OAuth app client initialized successfully
```

## Troubleshooting

### "Invalid client" Error

**Problem:** Your Client ID or Secret is incorrect

**Solution:**
1. Go back to Spotify Developer Dashboard
2. Click on your app → Settings
3. Copy the credentials again (make sure no extra spaces)
4. Update `app_config.json`

### "Redirect URI mismatch" Error

**Problem:** You didn't add the redirect URI

**Solution:**
1. Go to Spotify Developer Dashboard
2. Click on your app → Settings
3. Under "Redirect URIs", add: `http://localhost:8888/callback`
4. Click "Add" then "Save"

### Still Getting Rate Limits

**Problem:** You're still using the default shared credentials

**Solution:**
1. **Delete** the file `.spotify_oauth_cache` (if it exists)
2. Restart Syncra
3. The app will create a new cache file with YOUR credentials

## Alternative: Environment Variables

Instead of editing `app_config.json`, you can set environment variables:

### Windows (Command Prompt)
```cmd
set SP_APP_CLIENT_ID=your_client_id_here
set SP_APP_CLIENT_SECRET=your_client_secret_here
python main.py
```

### Windows (PowerShell)
```powershell
$env:SP_APP_CLIENT_ID="your_client_id_here"
$env:SP_APP_CLIENT_SECRET="your_client_secret_here"
python main.py
```

### Linux/Mac
```bash
export SP_APP_CLIENT_ID="your_client_id_here"
export SP_APP_CLIENT_SECRET="your_client_secret_here"
python main.py
```

## Security Notes

### Keep Your Credentials Private

⚠️ **Never share your Client Secret with anyone!**

- ❌ Don't post it in public forums
- ❌ Don't commit it to GitHub/public repos
- ❌ Don't share screenshots showing the secret
- ✅ Keep it in your local `app_config.json`

### What if Someone Gets My Credentials?

If your Client Secret is exposed:

1. Go to **Spotify Developer Dashboard**
2. Click on your app
3. Click **"Rotate client secret"** to generate a new one
4. Update your `app_config.json` with the new secret

## FAQ

### Q: Do I need to pay for a Spotify Developer account?
**A:** No! Spotify Developer accounts are **100% free**.

### Q: Will this affect my regular Spotify account?
**A:** No, this is completely separate. Your OAuth app just lets Syncra access public playlist data.

### Q: Can I use the same OAuth app on multiple computers?
**A:** Yes! Just copy your `app_config.json` to each computer.

### Q: What if I have a free Spotify account?
**A:** That's fine! OAuth apps work with both Free and Premium accounts.

### Q: Can I share my OAuth credentials with friends?
**A:** You can, but then you'll share the same rate limits. It's better for each person to create their own.

### Q: How do I know if I'm using my own credentials vs. the default ones?
**A:** Check your `app_config.json`. If you see credentials you added, those are yours. You can also check `.spotify_oauth_cache` - it will contain your Client ID.

## Need Help?

If you're still having trouble:

1. Check the [SPOTIFY_AUTH_SOLUTION.md](SPOTIFY_AUTH_SOLUTION.md) for technical details
2. Make sure your `sp_dc` cookie is fresh (not expired)
3. Try deleting `.spotify_oauth_cache` and restarting Syncra
4. Run `python test_spotify_auth.py` to diagnose the issue

---

**Last Updated:** December 31, 2025
**Difficulty:** Easy (5-10 minutes)
**Cost:** Free
