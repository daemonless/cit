# cit - Container Integration Test

A simple tool to verify daemonless containers actually work - not just start, but respond to health checks.

## Features

- FreeBSD + Podman (ocijail runtime)
- Auto-detects ready signal from container logs
- Auto-detects port from EXPOSE
- Screenshot capture with Selenium (~3 seconds)
- Screenshot verification with scikit-image (deterministic, no AI)

## Requirements

```sh
pkg install py311-selenium py311-scikit-image chromium
```

## Installation

```sh
# Download release
fetch -qo - https://github.com/daemonless/cit/releases/download/v0.1.0/cit-0.1.0.tar.gz | tar xz

# Or clone
git clone https://github.com/daemonless/cit.git
```

## Usage

```sh
# Basic test
./cit ghcr.io/daemonless/radarr:latest

# With options
./cit ghcr.io/daemonless/radarr:latest \
  --port 7878 \
  --health /ping \
  --annotation 'org.freebsd.jail.allow.mlock=true'

# With screenshot + verify
./cit ghcr.io/daemonless/radarr:latest \
  --screenshot /tmp/radarr.png \
  --verify

# Using repo config (.daemonless/config.yml)
./cit ghcr.io/daemonless/radarr:latest --repo /path/to/radarr
```

## Options

| Option | Description |
|--------|-------------|
| `--repo DIR` | Read config from DIR/.daemonless/config.yml |
| `--port PORT` | Port to test (default: auto-detect from EXPOSE) |
| `--health PATH` | Health endpoint (default: /) |
| `--wait SECONDS` | Timeout for ready signal (default: 30) |
| `--annotation K=V` | Add container annotation (repeatable) |
| `--keep` | Don't cleanup container after test |
| `--screenshot FILE` | Capture screenshot |
| `--tag TAG` | Image tag for per-tag baselines (e.g., `pkg`, `latest`) |
| `--verify` | Verify screenshot with scikit-image |
| `--verbose, -v` | Show detailed output |

## Repo Config

Place config in `.daemonless/config.yml`:

```
myapp/
├── Containerfile
└── .daemonless/
    ├── config.yml
    ├── baseline.png          # default baseline (for :latest)
    ├── baseline-pkg.png      # baseline for :pkg tag
    └── baseline-pkg-latest.png  # baseline for :pkg-latest tag
```

When using `--tag pkg`, cit looks for `baseline-pkg.png` first, then falls back to `baseline.png`.

**config.yml:**
```yaml
cit:
  port: 7878
  health: /ping
  wait: 30
  annotations:
    - org.freebsd.jail.allow.mlock=true
```

## GitHub Actions

```yaml
- name: Build in FreeBSD VM
  uses: vmactions/freebsd-vm@v1
  with:
    prepare: |
      pkg install -y podman py311-selenium py311-scikit-image chromium
    run: |
      # Build
      podman build -t localhost/myapp:test .

      # Fetch cit
      fetch -qo - https://github.com/daemonless/cit/releases/download/v0.1.0/cit-0.1.0.tar.gz | tar xz

      # Test
      ./cit-0.1.0/cit localhost/myapp:test --screenshot /tmp/test.png --verify
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Test passed |
| 1 | Test failed |

---

## How It Works

### Overview

cit performs end-to-end container testing in 5 phases:

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌────────────┐    ┌────────┐
│  Pull   │───▶│   Run   │───▶│  Wait   │───▶│   Health   │───▶│ Screen │
│  Image  │    │Container│    │  Ready  │    │   Check    │    │  shot  │
└─────────┘    └─────────┘    └─────────┘    └────────────┘    └────────┘
                                  │                                 │
                                  ▼                                 ▼
                            Log Patterns                      scikit-image
                            Detection                         Verification
```

### Phase 1: Pull Image

```sh
$RUNTIME pull "$IMAGE"
```

Pulls the image if not already present. Fails fast if image doesn't exist.

### Phase 2: Run Container

```sh
$RUNTIME run -d --name $CONTAINER_NAME --network podman $ANNOTATIONS "$IMAGE"
```

- Uses default `podman` bridge network (no custom network creation needed)
- Passes annotations for FreeBSD jail options (e.g., `allow.mlock` for .NET apps)
- Optionally mounts config directory: `-v $CONFIG_DIR:/config`

### Phase 3: Wait for Ready Signal

Instead of sleeping for a fixed time (slow and unreliable), cit watches container logs for ready patterns:

```sh
READY_PATTERNS="Warmup complete|services.d.*done|Application started|listening on"

while [ "$ELAPSED" -lt "$WAIT" ]; do
    if $RUNTIME logs "$CONTAINER_NAME" 2>&1 | grep -qE "$READY_PATTERNS"; then
        break
    fi
    sleep 1
done
```

**Ready patterns detected:**
| Pattern | Apps |
|---------|------|
| `Warmup complete` | Sonarr, Radarr, Prowlarr (Servarr apps) |
| `services.d.*done` | s6-overlay based images |
| `Application started` | .NET apps |
| `listening on` | Node.js, generic servers |

**Why this matters:** A Radarr container might take 15-20 seconds to be ready, but `services.d: done` appears at ~3 seconds. Fixed sleep wastes time; log watching is fast and reliable.

### Phase 4: Health Check

```sh
IP=$($RUNTIME inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_NAME")
URL="http://${IP}:${PORT}${HEALTH}"

fetch -qo /dev/null -T 5 "$URL"
```

- Gets container IP from network settings
- Makes HTTP request to health endpoint
- Uses `fetch` on FreeBSD (no curl dependency)
- 5 second timeout

**Port auto-detection:** If `--port` not specified, reads from image's `EXPOSE` directive:
```sh
PORT=$($RUNTIME inspect --format '{{range $p, $conf := .Config.ExposedPorts}}{{$p}} {{end}}' "$IMAGE" | awk -F/ '{print $1; exit}')
```

### Phase 5: Screenshot Capture (Optional)

Uses Selenium WebDriver for fast, reliable screenshots:

```
┌────────────────────────────────────────────────┐
│               screenshot.py                    │
├────────────────────────────────────────────────┤
│  1. Launch headless Chrome                     │
│  2. Navigate to container URL                  │
│  3. Wait for document.readyState == "complete" │
│  4. Brief pause (2s) for JS rendering          │
│  5. Save screenshot                            │
└────────────────────────────────────────────────┘
```

**Why Selenium over chromium CLI?**

| Method | Time | Issue |
|--------|------|-------|
| `chromium --screenshot --virtual-time-budget=10000` | ~20s | Fixed budget, can't detect actual page load |
| Selenium WebDriver | ~3s | Waits for real page load events |

**Environment variables:**
| Variable | Default | Description |
|----------|---------|-------------|
| `CHROME_BIN` | `/usr/local/bin/chrome` | Chrome binary path |
| `CHROMEDRIVER_BIN` | `/usr/local/bin/chromedriver` | ChromeDriver path |
| `SCREENSHOT_SIZE` | `1920,1080` | Window dimensions |

### Phase 6: Screenshot Verification (Optional)

Uses scikit-image for deterministic verification (no AI, no API calls):

```
┌───────────────────────────────────────────────────────────┐
│                        verify.py                          │
├───────────────────────────────────────────────────────────┤
│  Check 1: Is it blank?                                    │
│    - Convert to grayscale                                 │
│    - Calculate standard deviation                         │
│    - std < threshold → FAIL (blank/failed render)         │
│                                                           │
│  Check 2: Has UI elements?                                │
│    - Apply Sobel edge detection                           │
│    - Calculate edge pixel ratio                           │
│    - ratio < threshold → FAIL (no buttons/text/controls)  │
└───────────────────────────────────────────────────────────┘
```

**Thresholds (configurable via env):**
| Variable | Default | Description |
|----------|---------|-------------|
| `VERIFY_BLANK_THRESHOLD` | `10` | Grayscale std dev threshold |
| `VERIFY_EDGE_THRESHOLD` | `0.01` | Edge pixel ratio threshold |

**What it detects:**
- ✅ Normal app UI (buttons, text, navigation)
- ❌ Blank white/black screen (failed render)
- ❌ Solid color error page
- ❌ Empty page with no content

### File Structure

```
cit/
├── cit                 # Main shell script
├── screenshot.py       # Selenium screenshot helper
├── verify.py           # scikit-image verification
├── Makefile            # Build release tarball
└── README.md           # This file
```

### Runtime Detection

```sh
if [ "$(uname)" = "FreeBSD" ]; then
    if [ "$(id -u)" -ne 0 ]; then
        RUNTIME="doas podman"    # FreeBSD needs privilege escalation
    else
        RUNTIME="podman"
    fi
    FETCH_CMD="fetch -qo /dev/null -T 5"
elif command -v podman >/dev/null 2>&1; then
    RUNTIME="podman"
    FETCH_CMD="curl -sf -o /dev/null --max-time 5"
elif command -v docker >/dev/null 2>&1; then
    RUNTIME="docker"
    FETCH_CMD="curl -sf -o /dev/null --max-time 5"
fi
```

### Config Loading

When `--repo` is specified, cit loads config from `.daemonless/config.yml` (or `.daemonless.yml` for legacy repos):

```sh
# Parse YAML (simple grep-based, no dependencies)
# Config is under 'cit:' section
PORT=$(sed -n '/^cit:/,/^[^ ]/p' "$CIT_CONFIG" | grep 'port:' | awk '{print $2}')
HEALTH=$(sed -n '/^cit:/,/^[^ ]/p' "$CIT_CONFIG" | grep 'health:' | awk '{print $2}')
WAIT=$(sed -n '/^cit:/,/^[^ ]/p' "$CIT_CONFIG" | grep 'wait:' | awk '{print $2}')
```

CLI arguments always take precedence over config file values.

## License

BSD
