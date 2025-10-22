# Ngrok Setup - Share Your BigQuery MCP Server

Use ngrok to expose your local MCP server to the internet, allowing others to connect to it.

## Why Use Ngrok?

- **Share with team**: Let colleagues access your BigQuery server
- **Test remotely**: Connect from anywhere without deploying
- **Quick demos**: Show your setup to others instantly
- **Development**: Test webhooks and external integrations

## Prerequisites

1. Install ngrok: https://ngrok.com/download
2. Sign up for free account: https://dashboard.ngrok.com/signup
3. Get your auth token: https://dashboard.ngrok.com/get-started/your-authtoken

## Setup Steps

### 1. Install and Configure Ngrok

```bash
# Install ngrok (macOS)
brew install ngrok

# Or download from https://ngrok.com/download

# Configure auth token (one-time setup)
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### 2. Start Your MCP Server

```bash
# In terminal 1
cd ~/mcp-gbq
source venv/bin/activate
python server.py 8000
```

Server starts at `http://localhost:8000`

### 3. Start Ngrok Tunnel

```bash
# In terminal 2
ngrok http 8000
```

You'll see output like:
```
Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok-free.app -> http://localhost:8000

Connections                   ttl     opn     rt1     rt5     p50     p90
                              0       0       0.00    0.00    0.00    0.00
```

### 4. Share the URL

Your server is now accessible at: `https://abc123.ngrok-free.app`

**Share this URL** with others to let them connect to your BigQuery MCP server.

## Using with Desktop Agent

Others can connect using the ngrok URL:

```json
{
  "mcpServers": {
    "bigquery": {
      "url": "https://abc123.ngrok-free.app/mcp"
    }
  }
}
```

## Advanced Configuration

### Custom Subdomain (Paid Plans)

```bash
ngrok http 8000 --subdomain=my-bigquery-server
# URL: https://my-bigquery-server.ngrok.app
```

### Configuration File

Create `~/.ngrok2/ngrok.yml`:

```yaml
version: "2"
authtoken: YOUR_AUTH_TOKEN

tunnels:
  bigquery-mcp:
    proto: http
    addr: 8000
    subdomain: my-bigquery  # Requires paid plan
    inspect: true
```

Start with config:
```bash
ngrok start bigquery-mcp
```

### Basic Auth Protection

Add password protection:

```bash
ngrok http 8000 --basic-auth="username:password"
```

Users need to enter credentials when connecting.

### Regional Endpoints

Choose region closest to users:

```bash
# US
ngrok http 8000 --region=us

# Europe
ngrok http 8000 --region=eu

# Asia
ngrok http 8000 --region=ap

# Australia
ngrok http 8000 --region=au
```

## Monitoring

### Ngrok Web Interface

Access at: `http://localhost:4040`

Features:
- Real-time request logs
- Request/response inspection
- Replay requests
- Performance metrics

### View Active Tunnels

```bash
ngrok ls
```

### Tunnel Status

```bash
curl http://localhost:4040/api/tunnels
```

## Security Best Practices

### 1. Use Authentication

Always add basic auth for public URLs:

```bash
ngrok http 8000 --basic-auth="admin:secure_password_here"
```

### 2. Limit Access by IP (Paid Plans)

```yaml
tunnels:
  bigquery-mcp:
    proto: http
    addr: 8000
    ip_restriction:
      allow_cidrs:
        - 192.168.1.0/24
        - 10.0.0.0/8
```

### 3. Enable Request Inspection

Monitor who's accessing:

```bash
ngrok http 8000 --inspect=true
```

Check logs at `http://localhost:4040`

### 4. Temporary URLs

Free ngrok URLs change on restart - great for temporary sharing.

For permanent URLs, use paid plan with custom domains.

### 5. Environment Variables

Don't commit ngrok URLs to git:

```bash
# .env
NGROK_AUTH_TOKEN=your_token
NGROK_REGION=us
```

## Production Use

For production, consider:

1. **Ngrok Paid Plan** - Static domains, more bandwidth
2. **Deploy to Cloud** - Railway, Fly.io, Cloud Run
3. **VPN** - Tailscale or Cloudflare Tunnel for team access

## Troubleshooting

### Issue: "Failed to start tunnel"

**Solution:** Check if port 8000 is already in use:
```bash
lsof -i :8000
# Kill process if needed
kill -9 PID
```

### Issue: "ngrok not found"

**Solution:** Install ngrok:
```bash
# macOS
brew install ngrok

# Linux
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
  sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
  sudo tee /etc/apt/sources.list.d/ngrok.list && \
  sudo apt update && sudo apt install ngrok
```

### Issue: "Account limit exceeded"

**Solution:** Free plan limits:
- 1 online ngrok process
- 40 connections/minute
- 20 HTTP requests/second

Upgrade plan or stop other ngrok processes.

### Issue: Connection refused

**Solution:** Make sure your server is running on the correct port:
```bash
# Check server is running
curl http://localhost:8000/health

# Should return 200 OK
```

## Ngrok Alternatives

If ngrok doesn't work for you:

### Cloudflare Tunnel (Free)

```bash
# Install
brew install cloudflare/cloudflare/cloudflared

# Login
cloudflared login

# Start tunnel
cloudflared tunnel --url http://localhost:8000
```

### Tailscale (VPN for team)

```bash
# Install
curl -fsSL https://tailscale.com/install.sh | sh

# Start
sudo tailscale up

# Share with team (no public internet exposure)
```

### LocalTunnel (Free, no signup)

```bash
npm install -g localtunnel
lt --port 8000 --subdomain my-bigquery
```

## Example Use Cases

### 1. Team Demo

```bash
# You
python server.py 8000
ngrok http 8000

# Share URL with team
# Team adds to Desktop Agent config
```

### 2. Client Presentation

```bash
# With password protection
ngrok http 8000 --basic-auth="demo:demo123"

# Share URL and credentials with client
```

### 3. Remote Development

```bash
# Work from anywhere
ngrok http 8000 --region=us

# Access from laptop, tablet, phone
```

### 4. Integration Testing

```bash
# Expose to webhook services
ngrok http 8000

# Test external integrations without deploying
```

## Cost Comparison

| Feature | Free | Personal ($8/mo) | Pro ($20/mo) |
|---------|------|------------------|--------------|
| Online processes | 1 | 3 | 6 |
| Custom subdomain | ❌ | ✅ | ✅ |
| IP restrictions | ❌ | ❌ | ✅ |
| Custom domains | ❌ | ✅ | ✅ |
| Reserved domains | 0 | 1 | 3 |

For most development use, **free plan is sufficient**.

## See Also

- [Main README](readme.md) - Server setup
- [WSL Setup](WSL_SETUP.md) - Windows configuration
- [Ngrok Documentation](https://ngrok.com/docs)
