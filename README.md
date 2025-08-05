# FastCrate

A modern, opinionated FastAPI boilerplate for building high-performance APIs with best practices out of the box.

## Quick Start

```bash
git clone https://github.com/mubashirsidiki/FastCrate.git
cd FastCrate

# Install uv if not already installed
pip install uv

# Install dependencies
uv sync

# To add a new package
uv add package_name
# Example: uv add pandas

# Run the app
uv run python main.py
```

# Test the app

First go to http://localhost:8000/docs

GET `/api/v1/healthcheck` - Health Check


> ⚠️ If OneDrive causes issues, use:

```bash
uv sync --link-mode=copy
```

## Logger Service

If you want to use logger services visit:

http://localhost:8000/api/v1/logs

> 💡 **Note**: If after clicking the "Fetch Logs" button you see nothing, try switching to incognito mode in your browser.

