# Discord RPC Controller

API to control discord.py-self client for rich presence manipulation.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Server runs at `http://localhost:8000`

API docs at `http://localhost:8000/docs`

## API Endpoints

### Login
```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_DISCORD_TOKEN"}'
```

### Set Status
```bash
# online, idle, dnd, invisible
curl -X POST http://localhost:8000/status/update \
  -H "Content-Type: application/json" \
  -d '{"status": "dnd"}'
```

### Set Rich Presence
```bash
curl -X POST http://localhost:8000/rpc/set-rich-presence \
  -H "Content-Type: application/json" \
  -d '{
    "details": "Playing Game",
    "state": "In Match",
    "large_image": "game_icon",
    "large_text": "Awesome Game",
    "button1_label": "Play Now",
    "button1_url": "https://example.com"
  }'
```

### Set Custom Status
```bash
curl -X POST "http://localhost:8000/rpc/set-custom-status" \
  -H "Content-Type: application/json" \
  -d '{"emoji": "🎮", "text": "Gaming"}'
```

### Set Spotify
```bash
curl -X POST http://localhost:8000/rpc/spotify \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Song Title",
    "artists": ["Artist Name"],
    "album": "Album Name",
    "album_cover_url": "https://i.scdn.co/image/...",
    "track_id": "abc123",
    "duration_ms": 234000,
    "start_ms": 0
  }'
```

### Proxy External Images
```bash
curl -X POST "http://localhost:8000/rpc/proxy-images?application_id=123456&large_image_url=https://example.com/icon.png"
```

### Clear Presence
```bash
curl -X POST http://localhost:8000/clear
```

### Get Current Status
```bash
curl http://localhost:8000/status
```

### Logout
```bash
curl -X POST http://localhost:8000/logout
```

## Get Discord Token

1. Open Discord in browser
2. Press F12 → Application → Local Storage → discord.com
3. Find `token` field in localStorage

Or paste this in the console:
```javascript
(()=>{for(let e of Object.values(webpackChunkdiscord_app.push([[Symbol()],{},e=>e.c])))try{if(!e.exports||e.exports===window)continue;if(e.exports?.getToken)return e.exports.getToken();for(let t in e.exports)if(e.exports?.[t]?.getToken&&"IntlMessagesProxy"!==e.exports[t][Symbol.toStringTag])return e.exports[t].getToken()}catch{}})();
```
