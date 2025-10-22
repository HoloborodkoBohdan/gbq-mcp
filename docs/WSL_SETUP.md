# WSL Setup Guide for Desktop Agent

This guide explains how to set up the BigQuery MCP server on Windows using WSL (Windows Subsystem for Linux) with Desktop Agent.

## Prerequisites

- Windows 10/11 with WSL2 installed
- Desktop Agent for Windows
- Python 3.8+ in WSL

## Setup Steps

### 1. Install WSL (if not already installed)

```powershell
# In PowerShell (Administrator)
wsl --install
```

Restart your computer after installation.

### 2. Set up the project in WSL

```bash
# In WSL terminal
cd ~
git clone <your-repo-url> mcp-gbq
cd mcp-gbq

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Add your service account credentials

Place your `service-account.json` file in the project directory:

```bash
# In WSL
cd ~/mcp-gbq
# Copy your service account file here
```

### 4. Test the server

```bash
# In WSL
cd ~/mcp-gbq
source venv/bin/activate
python server.py --stdio
```

Press Ctrl+C to stop the test.

## Configuration for Desktop Agent

### Option 1: Direct WSL Command (Recommended)

Desktop Agent on Windows can run WSL commands directly.

**Configuration file location:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Configuration:**
```json
{
  "mcpServers": {
    "bigquery": {
      "command": "wsl",
      "args": [
        "bash",
        "-c",
        "cd /home/YOUR_USERNAME/mcp-gbq && source venv/bin/activate && python server.py --stdio"
      ]
    }
  }
}
```

**Important:** Replace `YOUR_USERNAME` with your actual WSL username.

To find your WSL username:
```bash
# In WSL terminal
whoami
```

### Option 2: HTTP Transport (Alternative)

If the direct WSL command doesn't work, use HTTP transport:

**Step 1:** Start the server in WSL

```bash
# In WSL terminal
cd ~/mcp-gbq
source venv/bin/activate
python server.py 8765
```

**Step 2:** Configure Desktop Agent

```json
{
  "mcpServers": {
    "bigquery": {
      "url": "http://localhost:8765"
    }
  }
}
```

**Note:** You'll need to keep the WSL terminal running with the server.

### Option 3: Automatic startup with systemd (Advanced)

Create a systemd service to auto-start the server:

```bash
# In WSL
sudo nano /etc/systemd/system/bigquery-mcp.service
```

```ini
[Unit]
Description=BigQuery MCP Server
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/mcp-gbq
Environment="PATH=/home/YOUR_USERNAME/mcp-gbq/venv/bin"
ExecStart=/home/YOUR_USERNAME/mcp-gbq/venv/bin/python server.py 8765
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable bigquery-mcp
sudo systemctl start bigquery-mcp
```

Then use the HTTP configuration (Option 2) in Desktop Agent.

## Troubleshooting

### Issue: "command not found: wsl"

**Solution:** Make sure WSL is installed and accessible from Windows PATH.

### Issue: "Permission denied"

**Solution:** Check file permissions in WSL:
```bash
chmod +x ~/mcp-gbq/server.py
```

### Issue: "Module not found"

**Solution:** Make sure virtual environment is activated:
```bash
cd ~/mcp-gbq
source venv/bin/activate
pip install -r requirements.txt
```

### Issue: Server not connecting

**Solution:**
1. Test server manually in WSL:
```bash
cd ~/mcp-gbq
source venv/bin/activate
python server.py --stdio
# Type a test and press Ctrl+D
```

2. Check Desktop Agent logs:
```
%APPDATA%\Claude\logs
```

### Issue: BigQuery authentication errors

**Solution:** Verify service account file:
```bash
# In WSL
cd ~/mcp-gbq
cat service-account.json | jq .project_id
```

Should output your project ID. If not, the JSON file is invalid.

## Verification

After configuring Desktop Agent:

1. Restart Desktop Agent
2. Open a new conversation
3. Look for the MCP server icon or indicator
4. Try asking: "What BigQuery tables do I have access to?"

If working correctly, Claude will use the `list_tables` tool and show available datasets.

## Performance Tips

### Speed up startup

Add this to your `~/.bashrc` in WSL:

```bash
# Quick alias for MCP server
alias mcp-bq='cd ~/mcp-gbq && source venv/bin/activate && python server.py'
```

### Keep server running

Use `tmux` or `screen` to keep the server running in the background:

```bash
# Install tmux
sudo apt install tmux

# Start server in tmux session
tmux new -s mcp
cd ~/mcp-gbq
source venv/bin/activate
python server.py 8765

# Detach: Press Ctrl+B, then D
# Reattach: tmux attach -t mcp
```

## WSL-Specific Notes

### File paths

- **Windows path:** `C:\Users\YourName\Documents`
- **WSL path:** `/mnt/c/Users/YourName/Documents`

### Networking

- WSL2 has its own network interface
- `localhost` from Windows connects to WSL2
- WSL2 can access Windows localhost at `$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')`

### Resource usage

WSL2 uses dynamic memory allocation. You can limit it by creating:

`%USERPROFILE%\.wslconfig`

```ini
[wsl2]
memory=4GB
processors=2
```

## Alternative: Use Windows Python Directly

If WSL causes issues, you can run Python directly on Windows:

1. Install Python for Windows
2. Install dependencies: `pip install -r requirements.txt`
3. Configure Desktop Agent:

```json
{
  "mcpServers": {
    "bigquery": {
      "command": "python",
      "args": ["C:\\path\\to\\mcp-gbq\\server.py", "--stdio"]
    }
  }
}
```

## Getting Help

If you encounter issues:

1. Check WSL status: `wsl --status`
2. Check Python version: `python3 --version`
3. Check dependencies: `pip list`
4. Test manually: `python server.py --stdio`
5. Check Desktop Agent logs in `%APPDATA%\Claude\logs`

## See Also

- [Main README](readme.md) - General setup and features
- [Architecture](ARCHITECTURE.md) - System architecture
- [BigQuery Authentication](https://cloud.google.com/bigquery/docs/authentication)
