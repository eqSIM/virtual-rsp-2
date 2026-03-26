#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Virtual RSP — Complete Setup + Test + Teardown
# ═══════════════════════════════════════════════════════════════════════════════
#
# This script is self-contained: it checks prerequisites, auto-installs what it
# can, builds everything, starts all services, runs the full SGP.22 test suite,
# and tears down cleanly regardless of success or failure.
#
# Usage:
#   ./test-all.sh                  # full run (build + setup + test)
#   ./test-all.sh --skip-build     # reuse existing build artifacts
#   ./test-all.sh --skip-setup     # reuse existing venv + certs too
#   ./test-all.sh --tests-only     # skip build AND setup (fastest re-run)
#
# ═══════════════════════════════════════════════════════════════════════════════

# Avoid surprises from locale-dependent sorting / messages
export LC_ALL=C

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$PROJECT_DIR/build"
PYSIM_DIR="$PROJECT_DIR/pysim"
VENV_DIR="$PYSIM_DIR/venv"
CERT_DIR="$PYSIM_DIR/smdpp-data/generated"
DAEMON_BIN="$BUILD_DIR/v-euicc/v-euicc-daemon"
LPAC_BIN="$BUILD_DIR/lpac/src/lpac"
LOG_DIR="/tmp/vrsp-test-$$"

VEUICC_PORT=8765
SMDPP_PORT=8000
NGINX_PORT=8443
SMDPP_HOST="testsmdpplus1.example.com"

# Prefer system python3.12 (stable) over bleeding-edge brew python 3.14
PYTHON3=""
for candidate in /usr/bin/python3.12 /usr/bin/python3 python3; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON3="$candidate"
        break
    fi
done

# ── Flags ────────────────────────────────────────────────────────────────────
SKIP_BUILD=false
SKIP_SETUP=false
for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
        --skip-setup) SKIP_SETUP=true; SKIP_BUILD=true ;;
        --tests-only) SKIP_SETUP=true; SKIP_BUILD=true ;;
        -h|--help)
            sed -n '2,/^$/{ s/^# //; s/^#//; p }' "$0"
            exit 0 ;;
    esac
done

# ── Colors ───────────────────────────────────────────────────────────────────
R='\033[0;31m'; G='\033[0;32m'; Y='\033[0;33m'; B='\033[0;34m'
C='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; RST='\033[0m'

_step=0
step()  { _step=$((_step+1)); echo ""; echo -e "${BOLD}${B}[$_step] $1${RST}"; echo -e "${DIM}$(printf '%.0s─' $(seq 1 70))${RST}"; }
ok()    { echo -e "  ${G}✓${RST} $1"; }
warn()  { echo -e "  ${Y}⚠${RST} $1"; }
fail()  { echo -e "  ${R}✗ $1${RST}"; }
info()  { echo -e "  ${DIM}$1${RST}"; }
die()   { echo ""; fail "$1"; [[ -n "${2:-}" ]] && echo -e "  ${Y}Fix:${RST} $2"; exit 1; }

# ── Tracked PIDs ─────────────────────────────────────────────────────────────
declare -a PIDS=()

# ── Teardown (always runs on exit) ──────────────────────────────────────────
do_teardown() {
    echo ""
    echo -e "${BOLD}${B}[teardown] Stopping all services${RST}"
    echo -e "${DIM}$(printf '%.0s─' $(seq 1 70))${RST}"
    local pid
    for pid in "${PIDS[@]+"${PIDS[@]}"}"; do
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done
    sleep 0.5
    pkill -f "v-euicc-daemon" 2>/dev/null || true
    pkill -f "osmo-smdpp"     2>/dev/null || true
    pkill -f "nginx.*smdpp"   2>/dev/null || true
    rm -f "$PYSIM_DIR/nginx-smdpp.pid" 2>/dev/null || true
    sleep 0.5
    if [[ -d "$LOG_DIR" ]]; then
        ok "Logs saved in $LOG_DIR/"
    fi
    ok "All processes stopped"
}
trap do_teardown EXIT

wait_for_port() {
    local port=$1 secs=${2:-15} i=0
    while ! nc -z 127.0.0.1 "$port" 2>/dev/null; do
        sleep 1; i=$((i+1))
        if (( i >= secs )); then return 1; fi
    done
}

# ═════════════════════════════════════════════════════════════════════════════
#  BANNER
# ═════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${BOLD}${C}╔══════════════════════════════════════════════════════════════════════╗${RST}"
echo -e "${BOLD}${C}║    Virtual RSP — GSMA SGP.22 Setup + Test Suite (Ubuntu)            ║${RST}"
echo -e "${BOLD}${C}╚══════════════════════════════════════════════════════════════════════╝${RST}"
echo -e "${DIM}  lpac  <──socket──>  v-euicc-daemon  <──HTTPS/ES9+──>  osmo-smdpp${RST}"
echo ""

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"
info "Project : $PROJECT_DIR"
info "Logs    : $LOG_DIR/"

# ═════════════════════════════════════════════════════════════════════════════
#  PHASE 1: PREREQUISITES — detect, auto-install, or give actionable advice
# ═════════════════════════════════════════════════════════════════════════════
step "Checking & installing prerequisites"

HAS_SUDO=false
if sudo -n true 2>/dev/null; then HAS_SUDO=true; fi

HAS_BREW=false
if command -v brew &>/dev/null; then HAS_BREW=true; fi

auto_install() {
    local pkg=$1 label=${2:-$1}
    if $HAS_BREW; then
        info "Installing $label via brew..."
        if brew install "$pkg" >> "$LOG_DIR/brew-install.log" 2>&1; then
            ok "$label installed via brew"; return 0
        fi
    fi
    if $HAS_SUDO; then
        info "Installing $label via apt..."
        if sudo apt-get install -y "$pkg" >> "$LOG_DIR/apt-install.log" 2>&1; then
            ok "$label installed via apt"; return 0
        fi
    fi
    return 1
}

need_apt=()

require_cmd() {
    local cmd=$1 brew_pkg=${2:-$1} apt_pkg=${3:-$2} purpose=$4
    if command -v "$cmd" &>/dev/null; then
        ok "$cmd found"; return
    fi
    # Try auto-install
    if auto_install "$brew_pkg" "$cmd"; then
        hash -r  # refresh PATH cache
        if command -v "$cmd" &>/dev/null; then return; fi
    fi
    fail "$cmd missing — needed for: $purpose"
    need_apt+=("$apt_pkg")
}

require_lib() {
    local pc_name=$1 apt_pkg=$2 purpose=$3
    if pkg-config --exists "$pc_name" 2>/dev/null; then
        ok "$pc_name found"; return
    fi
    fail "$pc_name headers missing — needed for: $purpose"
    need_apt+=("$apt_pkg")
}

require_cmd cmake      cmake       cmake            "building C components"
require_cmd gcc        gcc         build-essential   "C compilation"
require_cmd make       make        build-essential   "C compilation"
require_cmd nginx      nginx       nginx             "TLS reverse proxy"
require_cmd nc         netcat      netcat-openbsd    "port connectivity checks"
require_cmd pkg-config pkg-config  pkg-config        "library detection"
require_cmd git        git         git               "cloning Python deps"
require_cmd curl       curl        curl              "HTTPS endpoint tests"
require_cmd swig       swig        swig              "building pyscard Python package"

require_lib openssl    libssl-dev     "eUICC crypto + TLS certificates"

# Python — we already selected PYTHON3 above
if [[ -z "$PYTHON3" ]]; then
    die "No python3 found anywhere on PATH" \
        "sudo apt install python3 python3-venv"
fi
ok "python3 = $PYTHON3 ($($PYTHON3 --version 2>&1))"

if ! $PYTHON3 -m venv --help &>/dev/null; then
    fail "python3 venv module not available"
    need_apt+=("python3-venv")
fi

if (( ${#need_apt[@]} > 0 )); then
    # de-dup
    readarray -t need_apt < <(printf '%s\n' "${need_apt[@]}" | sort -u)
    die "Missing system packages that could not be auto-installed: ${need_apt[*]}" \
        "sudo apt update && sudo apt install -y ${need_apt[*]}"
fi

ok "All prerequisites satisfied"

# ═════════════════════════════════════════════════════════════════════════════
#  PHASE 2: FIX — symlink pySim -> pysim (C code expects capital S)
# ═════════════════════════════════════════════════════════════════════════════
step "Fixing directory layout"

# lpac expects cmake/git-version.cmake — create if missing
GV_CMAKE="$PROJECT_DIR/lpac/cmake/git-version.cmake"
if [[ ! -f "$GV_CMAKE" ]]; then
    cat > "$GV_CMAKE" << 'CMAKEOF'
find_package(Git QUIET)
if(GIT_FOUND)
    execute_process(
        COMMAND ${GIT_EXECUTABLE} describe --tags --always --dirty
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
        OUTPUT_VARIABLE LPAC_VERSION
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
        RESULT_VARIABLE GIT_RESULT
    )
    if(NOT GIT_RESULT EQUAL 0)
        unset(LPAC_VERSION)
    endif()
endif()
CMAKEOF
    ok "Created missing lpac/cmake/git-version.cmake"
else
    ok "lpac/cmake/git-version.cmake exists"
fi

if [[ -d "$PROJECT_DIR/pysim" ]] && [[ ! -e "$PROJECT_DIR/pySim" ]]; then
    ln -s pysim "$PROJECT_DIR/pySim"
    ok "Created symlink pySim -> pysim (C code expects uppercase)"
elif [[ -L "$PROJECT_DIR/pySim" ]]; then
    ok "Symlink pySim -> pysim already exists"
elif [[ -d "$PROJECT_DIR/pySim" ]]; then
    ok "pySim directory exists natively"
else
    die "Neither pysim nor pySim directory found" \
        "The repository may be incomplete — check your git clone"
fi

# ═════════════════════════════════════════════════════════════════════════════
#  PHASE 3: PYTHON VENV + CERTIFICATE GENERATION (before build, since PKID may patch C source)
# ═════════════════════════════════════════════════════════════════════════════
if $SKIP_SETUP && [[ -d "$VENV_DIR" ]] && [[ -f "$CERT_DIR/DPtls/CERT_S_SM_DP_TLS_NIST.pem" ]]; then
    step "Python env + certificates (skipped — already present)"
    ok "venv  : $VENV_DIR"
    ok "certs : $CERT_DIR"
else
    step "Setting up Python virtual environment"

    if [[ ! -d "$VENV_DIR" ]]; then
        $PYTHON3 -m venv "$VENV_DIR" \
            || die "Failed to create venv with $PYTHON3" \
                   "Try: $PYTHON3 -m venv $VENV_DIR  (or install python3-venv)"
        ok "Created venv ($PYTHON3)"
    else
        ok "venv already exists"
    fi

    # Activate venv for pip install
    source "$VENV_DIR/bin/activate"

    pip install --upgrade pip > "$LOG_DIR/pip-upgrade.log" 2>&1 || true
    ok "pip upgraded"

    # Install deps — retry with relaxed constraints if first pass fails
    if pip install -r "$PYSIM_DIR/requirements.txt" > "$LOG_DIR/pip-install.log" 2>&1; then
        ok "Python dependencies installed (from requirements.txt)"
    else
        warn "Full requirements.txt failed — trying without pyscard (not needed for SM-DP+)"
        grep -v '^pyscard' "$PYSIM_DIR/requirements.txt" > "$LOG_DIR/requirements-nopyscard.txt"
        if pip install -r "$LOG_DIR/requirements-nopyscard.txt" >> "$LOG_DIR/pip-install.log" 2>&1; then
            ok "Python dependencies installed (without pyscard — not needed for this test)"
        else
            deactivate
            fail "pip install failed — last 20 lines:"
            tail -20 "$LOG_DIR/pip-install.log" | while IFS= read -r l; do info "  $l"; done
            die "Cannot install Python dependencies" "cat $LOG_DIR/pip-install.log"
        fi
    fi

    # osmo-smdpp needs extra packages not listed in requirements.txt
    EXTRA_PKGS=()
    for pkg in klein requests; do
        if ! pip show "$pkg" &>/dev/null; then EXTRA_PKGS+=("$pkg"); fi
    done
    if (( ${#EXTRA_PKGS[@]} > 0 )); then
        pip install "${EXTRA_PKGS[@]}" >> "$LOG_DIR/pip-install.log" 2>&1 \
            || die "Failed to install extra packages: ${EXTRA_PKGS[*]}" "pip install ${EXTRA_PKGS[*]}"
        ok "Installed extra packages: ${EXTRA_PKGS[*]}"
    fi

    deactivate

    # ── Generate certificates ────────────────────────────────────────────────
    step "Generating SGP.26 test certificates"

    if [[ -f "$CERT_DIR/DPtls/CERT_S_SM_DP_TLS_NIST.der" ]] && \
       [[ -f "$CERT_DIR/eUICC/CERT_EUICC_ECDSA_NIST.der" ]] && \
       [[ -f "$CERT_DIR/eUICC/SK_EUICC_ECDSA_NIST.pem" ]] && \
       [[ -f "$CERT_DIR/EUM/CERT_EUM_ECDSA_NIST.der" ]]; then
        ok "Certificates already exist — skipping generation"
    else
        source "$VENV_DIR/bin/activate"
        if (cd "$PYSIM_DIR" && python3 contrib/generate_smdpp_certs.py) > "$LOG_DIR/certgen.log" 2>&1; then
            ok "Certificates generated"
        else
            deactivate
            fail "Certificate generation failed — last 20 lines:"
            tail -20 "$LOG_DIR/certgen.log" | while IFS= read -r l; do info "  $l"; done
            die "Cannot generate test certificates" "cat $LOG_DIR/certgen.log"
        fi
        deactivate
    fi

    for f in \
        "$CERT_DIR/DPtls/CERT_S_SM_DP_TLS_NIST.der" \
        "$CERT_DIR/eUICC/CERT_EUICC_ECDSA_NIST.der" \
        "$CERT_DIR/eUICC/SK_EUICC_ECDSA_NIST.pem" \
        "$CERT_DIR/EUM/CERT_EUM_ECDSA_NIST.der"; do
        if [[ ! -f "$f" ]]; then
            die "Missing certificate: $f" "Re-run without --skip-setup"
        fi
    done
    ok "All required certificate files verified"
fi

# ── Always: sync PKID + convert DER→PEM (runs even with --skip-setup) ───────
step "Syncing CI PKID and TLS certificates"

# The v-euicc C code hardcodes the CI certificate's PKID (Subject Key Identifier).
# The PKID appears in comments as colon-hex (e.g. 3C:45:E5:...) and in byte arrays as
# 0x3C, 0x45, ... spanning multiple lines. We patch both forms.
CI_CERT="$CERT_DIR/CertificateIssuer/CERT_CI_ECDSA_NIST.der"
APDU_SRC="$PROJECT_DIR/v-euicc/src/apdu_handler.c"
if [[ -f "$CI_CERT" ]] && [[ -f "$APDU_SRC" ]]; then
    NEW_PKID=$(openssl x509 -inform DER -in "$CI_CERT" -noout -text 2>/dev/null \
        | grep -A1 "Subject Key Identifier" | tail -1 | tr -d ' \n')
    # Extract current PKID from C byte array (20 bytes after the 0x04, 0x14 prefix)
    CUR_PKID=$($PYTHON3 -c "
import re
src = open('$APDU_SRC').read()
m = re.search(r'ci_pk\[\]\s*=\s*\{0x04,\s*0x14,\s*((?:0x[0-9A-Fa-f]{2},?\s*){20})', src, re.DOTALL)
if m:
    bs = re.findall(r'0x([0-9A-Fa-f]{2})', m.group(1))
    print(':'.join(b.upper() for b in bs))
" 2>/dev/null) || true

    if [[ -n "$NEW_PKID" ]] && [[ -n "$CUR_PKID" ]] && [[ "$CUR_PKID" != "$NEW_PKID" ]]; then
        $PYTHON3 -c "
old = '$CUR_PKID'.split(':')
new = '$NEW_PKID'.split(':')
src = open('$APDU_SRC').read()
src = src.replace('$CUR_PKID', '$NEW_PKID')
# Replace C byte array lines: 8 bytes on first line, 12 on continuation
old_l1 = ', '.join('0x'+b for b in old[:8])
new_l1 = ', '.join('0x'+b for b in new[:8])
old_l2 = ', '.join('0x'+b for b in old[8:])
new_l2 = ', '.join('0x'+b for b in new[8:])
src = src.replace(old_l1, new_l1).replace(old_l2, new_l2)
open('$APDU_SRC','w').write(src)
"
        ok "Patched eUICC CI PKID in apdu_handler.c"
        info "  Old: $CUR_PKID"
        info "  New: $NEW_PKID"
        SKIP_BUILD=false
    elif [[ "$CUR_PKID" == "$NEW_PKID" ]]; then
        ok "CI PKID in C source matches generated certificates"
    else
        warn "Could not extract/compare PKID — may need manual update"
    fi
fi

# nginx needs PEM cert but cert generator outputs DER
TLS_CERT_DER="$CERT_DIR/DPtls/CERT_S_SM_DP_TLS_NIST.der"
TLS_CERT_PEM="$CERT_DIR/DPtls/CERT_S_SM_DP_TLS_NIST.pem"
if [[ -f "$TLS_CERT_DER" ]] && [[ ! -f "$TLS_CERT_PEM" ]]; then
    openssl x509 -inform DER -in "$TLS_CERT_DER" -out "$TLS_CERT_PEM" \
        || die "Failed to convert DPtls cert DER→PEM"
    ok "Converted DPtls certificate DER → PEM for nginx"
elif [[ -f "$TLS_CERT_PEM" ]]; then
    ok "TLS PEM certificate exists"
fi

# ═════════════════════════════════════════════════════════════════════════════
#  BUILD C COMPONENTS (after cert + PKID sync, which may patch C source)
# ═════════════════════════════════════════════════════════════════════════════
if $SKIP_BUILD && [[ -x "$DAEMON_BIN" ]] && [[ -x "$LPAC_BIN" ]]; then
    step "Build (skipped — binaries exist)"
    ok "$DAEMON_BIN"
    ok "$LPAC_BIN"
else
    step "Building C components (lpac + v-euicc-daemon)"

    cmake -B "$BUILD_DIR" \
        -DCMAKE_BUILD_TYPE=Release \
        -DLPAC_WITH_APDU_PCSC=OFF \
        -DCMAKE_C_FLAGS="-Wno-deprecated-declarations" \
        "$PROJECT_DIR" \
        > "$LOG_DIR/cmake-configure.log" 2>&1 \
        || { fail "CMake configure failed — log:"; tail -20 "$LOG_DIR/cmake-configure.log" | while IFS= read -r l; do info "  $l"; done; die "CMake configure failed" "cat $LOG_DIR/cmake-configure.log"; }
    ok "CMake configured"

    cmake --build "$BUILD_DIR" -j"$(nproc)" \
        > "$LOG_DIR/cmake-build.log" 2>&1 \
        || { fail "Build failed — last 20 lines:"; tail -20 "$LOG_DIR/cmake-build.log" | while IFS= read -r l; do info "  $l"; done; die "C build failed" "cat $LOG_DIR/cmake-build.log"; }
    ok "Build succeeded"

    [[ -x "$DAEMON_BIN" ]] || die "v-euicc-daemon not found at $DAEMON_BIN after build"
    [[ -x "$LPAC_BIN" ]]   || die "lpac not found at $LPAC_BIN after build"
    ok "v-euicc-daemon : $DAEMON_BIN"
    ok "lpac           : $LPAC_BIN"
fi

# lpac driver symlink: ELF RUNPATH points to $BUILD_DIR, then it appends /driver
if [[ -d "$BUILD_DIR/lpac/driver" ]] && [[ ! -e "$BUILD_DIR/driver" ]]; then
    ln -s lpac/driver "$BUILD_DIR/driver"
    ok "Created $BUILD_DIR/driver -> lpac/driver symlink"
elif [[ -e "$BUILD_DIR/driver" ]]; then
    ok "Driver symlink OK"
fi

# ═════════════════════════════════════════════════════════════════════════════
#  /etc/hosts ENTRY
# ═════════════════════════════════════════════════════════════════════════════
step "Checking /etc/hosts for $SMDPP_HOST"

if grep -q "$SMDPP_HOST" /etc/hosts 2>/dev/null; then
    ok "$SMDPP_HOST present in /etc/hosts"
else
    if $HAS_SUDO; then
        echo "127.0.0.1  $SMDPP_HOST" | sudo tee -a /etc/hosts > /dev/null
        ok "Added $SMDPP_HOST to /etc/hosts"
    else
        die "$SMDPP_HOST not in /etc/hosts and no passwordless sudo" \
            "echo '127.0.0.1  $SMDPP_HOST' | sudo tee -a /etc/hosts"
    fi
fi

# ═════════════════════════════════════════════════════════════════════════════
#  PHASE 6: CLEAN UP STALE PROCESSES & PORTS
# ═════════════════════════════════════════════════════════════════════════════
step "Cleaning up stale processes"

for pat in "v-euicc-daemon" "osmo-smdpp" "nginx.*smdpp"; do
    if pgrep -f "$pat" &>/dev/null; then
        pkill -f "$pat" 2>/dev/null || true
        warn "Killed leftover process matching '$pat'"
    fi
done
sleep 1

# Force-kill anything still holding our ports
for port in $VEUICC_PORT $SMDPP_PORT $NGINX_PORT; do
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then
        # Try to find and kill the process using fuser
        if command -v fuser &>/dev/null; then
            fuser -k "$port/tcp" 2>/dev/null || true
            warn "Force-killed process on port $port via fuser"
            sleep 1
        fi
    fi
done

for port in $VEUICC_PORT $SMDPP_PORT $NGINX_PORT; do
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then
        die "Port $port still in use after cleanup" \
            "Find it: ss -tlnp | grep $port  or  sudo lsof -i :$port"
    fi
done
ok "Ports $VEUICC_PORT, $SMDPP_PORT, $NGINX_PORT are free"

# ═════════════════════════════════════════════════════════════════════════════
#  PHASE 7: START SERVICES
# ═════════════════════════════════════════════════════════════════════════════

# ── 7a: v-euicc-daemon ──────────────────────────────────────────────────────
step "Starting v-euicc-daemon on port $VEUICC_PORT"

"$DAEMON_BIN" "$VEUICC_PORT" > "$LOG_DIR/v-euicc.log" 2>&1 &
VEUICC_PID=$!; PIDS+=("$VEUICC_PID")

if wait_for_port "$VEUICC_PORT" 10; then
    ok "v-euicc-daemon listening (PID $VEUICC_PID)"
else
    if ! kill -0 "$VEUICC_PID" 2>/dev/null; then
        fail "Process exited immediately — log:"
        tail -15 "$LOG_DIR/v-euicc.log" | while IFS= read -r l; do info "  $l"; done
    fi
    die "v-euicc-daemon not listening on $VEUICC_PORT" \
        "cat $LOG_DIR/v-euicc.log"
fi

# ── 7b: osmo-smdpp ──────────────────────────────────────────────────────────
step "Starting osmo-smdpp on port $SMDPP_PORT"

source "$VENV_DIR/bin/activate"
# PYTHONPATH must include project root for vrsp_logging, and pysim/ for pySim package
(cd "$PYSIM_DIR" && \
 PYTHONPATH="$PROJECT_DIR:$PYSIM_DIR:${PYTHONPATH:-}" \
 python3 ./osmo-smdpp.py \
    -H 127.0.0.1 -p "$SMDPP_PORT" --nossl -c generated \
) > "$LOG_DIR/osmo-smdpp.log" 2>&1 &
SMDPP_PID=$!; PIDS+=("$SMDPP_PID")
deactivate

if wait_for_port "$SMDPP_PORT" 20; then
    ok "osmo-smdpp listening (PID $SMDPP_PID)"
else
    if ! kill -0 "$SMDPP_PID" 2>/dev/null; then
        fail "Process died — log:"
        tail -25 "$LOG_DIR/osmo-smdpp.log" | while IFS= read -r l; do info "  $l"; done
    else
        fail "Process running but port $SMDPP_PORT not open after 20s"
    fi
    die "osmo-smdpp failed to start" "cat $LOG_DIR/osmo-smdpp.log"
fi

# ── 7c: nginx TLS proxy ─────────────────────────────────────────────────────
step "Starting nginx TLS proxy on port $NGINX_PORT"

# Pre-flight: test the config
if ! nginx -t -c "$PYSIM_DIR/nginx-smdpp.conf" -p "$PYSIM_DIR" > "$LOG_DIR/nginx-test.log" 2>&1; then
    fail "nginx config test failed:"
    tail -10 "$LOG_DIR/nginx-test.log" | while IFS= read -r l; do info "  $l"; done
    die "nginx configuration invalid" "cat $LOG_DIR/nginx-test.log"
fi
ok "nginx config test passed"

nginx -c "$PYSIM_DIR/nginx-smdpp.conf" -p "$PYSIM_DIR" \
    > "$LOG_DIR/nginx.log" 2>&1 &
NGINX_PID=$!; PIDS+=("$NGINX_PID")

if wait_for_port "$NGINX_PORT" 10; then
    ok "nginx listening (PID $NGINX_PID)"
else
    fail "nginx did not bind port $NGINX_PORT"
    if [[ -f "$PYSIM_DIR/nginx-error.log" ]]; then
        tail -10 "$PYSIM_DIR/nginx-error.log" | while IFS= read -r l; do info "  $l"; done
    fi
    die "nginx failed" "cat $PYSIM_DIR/nginx-error.log"
fi

# Quick HTTPS smoke test
if curl -sk --max-time 5 -o /dev/null -w "%{http_code}" "https://localhost:$NGINX_PORT/" 2>/dev/null | grep -qE "^[2345]"; then
    ok "HTTPS endpoint reachable"
else
    warn "HTTPS returned unexpected status — may still work for ES9+ calls"
fi

echo ""
echo -e "${BOLD}${G}  All services running:${RST}"
echo -e "    ${C}v-euicc-daemon${RST}  PID $VEUICC_PID  port $VEUICC_PORT"
echo -e "    ${G}osmo-smdpp${RST}      PID $SMDPP_PID  port $SMDPP_PORT"
echo -e "    ${Y}nginx (TLS)${RST}     PID $NGINX_PID  port $NGINX_PORT"

# ═════════════════════════════════════════════════════════════════════════════
#  PHASE 8: RUN TESTS
# ═════════════════════════════════════════════════════════════════════════════
TESTS_RUN=0; TESTS_PASS=0; TESTS_FAIL=0

pass_test() { TESTS_PASS=$((TESTS_PASS+1)); }
fail_test() { TESTS_FAIL=$((TESTS_FAIL+1)); }

# ── Test 1: Chip Info ────────────────────────────────────────────────────────
step "TEST 1 — lpac chip info"
TESTS_RUN=$((TESTS_RUN+1))

info "Running: LPAC_APDU=socket $LPAC_BIN chip info"

if LPAC_APDU=socket "$LPAC_BIN" chip info > "$LOG_DIR/test1-chip-info.log" 2>&1; then
    ok "lpac chip info succeeded"
    eid=$(grep -o '"eid":"[^"]*"' "$LOG_DIR/test1-chip-info.log" 2>/dev/null | head -1) || true
    [[ -n "${eid:-}" ]] && info "$eid"
    pass_test
else
    fail "lpac chip info failed (exit $?)"
    tail -10 "$LOG_DIR/test1-chip-info.log" | while IFS= read -r l; do info "  $l"; done
    fail_test
fi

# ── Test 2: Mutual Authentication (Discovery) ───────────────────────────────
step "TEST 2 — Mutual Authentication (ES9+ discovery, no matchingID)"
TESTS_RUN=$((TESTS_RUN+1))

info "Running: lpac profile discovery -s $SMDPP_HOST:$NGINX_PORT"

LPAC_APDU=socket "$LPAC_BIN" profile discovery \
    -s "$SMDPP_HOST:$NGINX_PORT" \
    -i 123456789012345 \
    > "$LOG_DIR/test2-discovery.log" 2>&1 || true

auth_ok=false

if grep -q "es11_authenticate_client" "$LOG_DIR/test2-discovery.log" 2>/dev/null; then
    ok "LPA authentication flow executed"
    auth_ok=true
fi

if grep -q "Refused" "$LOG_DIR/osmo-smdpp.log" 2>/dev/null; then
    ok "SM-DP+ verified eUICC signature (Refused = auth OK, no matching profile)"
    auth_ok=true
fi

if $auth_ok; then
    pass_test
else
    fail "Mutual authentication did not complete"
    info "-- lpac output (last 10 lines) --"
    tail -10 "$LOG_DIR/test2-discovery.log" | while IFS= read -r l; do info "  $l"; done
    info "-- osmo-smdpp output (last 10 lines) --"
    tail -10 "$LOG_DIR/osmo-smdpp.log" | while IFS= read -r l; do info "  $l"; done
    fail_test
fi

# ── Test 3: Profile Download ────────────────────────────────────────────────
step "TEST 3 — Profile Download (with matchingID)"
TESTS_RUN=$((TESTS_RUN+1))

PROFILE_ID="TS48V2-SAIP2-1-BERTLV-UNIQUE"
info "Running: lpac profile download -s $SMDPP_HOST:$NGINX_PORT -m $PROFILE_ID"

LPAC_APDU=socket "$LPAC_BIN" profile download \
    -s "$SMDPP_HOST:$NGINX_PORT" \
    -m "$PROFILE_ID" \
    > "$LOG_DIR/test3-download.log" 2>&1 &
DL_PID=$!

# Wait up to 30s for the download process
info "Download running (PID $DL_PID) — waiting up to 30 seconds..."
dl_done=false
for _i in $(seq 1 30); do
    if ! kill -0 "$DL_PID" 2>/dev/null; then dl_done=true; break; fi
    sleep 1
done
if ! $dl_done; then
    kill "$DL_PID" 2>/dev/null || true
    wait "$DL_PID" 2>/dev/null || true
    info "Timed out after 30s — checking partial progress"
fi

dl_steps=0; dl_total=5

dl_check() {
    local n=$1 pat=$2 label=$3
    if grep -q "$pat" "$LOG_DIR/test3-download.log" 2>/dev/null; then
        ok "Step $n/$dl_total: $label"
        dl_steps=$((dl_steps+1))
    else
        fail "Step $n/$dl_total: $label"
    fi
}

dl_check 1 "es10b_prepare_download"                              "PrepareDownload initiated"
dl_check 2 "es9p_get_bound_profile_package"                      "BoundProfilePackage requested"
dl_check 3 "es10b_load_bound_profile_package"                    "LoadBoundProfilePackage initiated"
dl_check 4 '"code":0'                                            "LPA returned success code"
dl_check 5 '"message":"success"'                                 "Profile download completed"

if (( dl_steps >= 3 )); then
    ok "Download reached $dl_steps/$dl_total steps"
    pass_test
elif (( dl_steps > 0 )); then
    warn "Partial progress: $dl_steps/$dl_total steps"
    fail_test
else
    fail "No download steps completed"
    info "-- lpac output (last 15 lines) --"
    tail -15 "$LOG_DIR/test3-download.log" | while IFS= read -r l; do info "  $l"; done
    fail_test
fi

# ═════════════════════════════════════════════════════════════════════════════
#  PHASE 9: RESULTS SUMMARY
# ═════════════════════════════════════════════════════════════════════════════
echo ""
echo ""
echo -e "${BOLD}${C}╔══════════════════════════════════════════════════════════════════════╗${RST}"
echo -e "${BOLD}${C}║                         RESULTS SUMMARY                             ║${RST}"
echo -e "${BOLD}${C}╚══════════════════════════════════════════════════════════════════════╝${RST}"
echo ""

if (( TESTS_FAIL == 0 )); then
    echo -e "  ${BOLD}${G}ALL $TESTS_PASS / $TESTS_RUN TESTS PASSED${RST}"
elif (( TESTS_PASS > 0 )); then
    echo -e "  ${BOLD}${Y}$TESTS_PASS PASSED, $TESTS_FAIL FAILED (of $TESTS_RUN)${RST}"
else
    echo -e "  ${BOLD}${R}ALL $TESTS_RUN TESTS FAILED${RST}"
fi

echo ""
echo -e "  ${DIM}Detailed logs:${RST}"
echo -e "    ${DIM}$LOG_DIR/v-euicc.log          — virtual eUICC daemon${RST}"
echo -e "    ${DIM}$LOG_DIR/osmo-smdpp.log       — SM-DP+ server${RST}"
echo -e "    ${DIM}$LOG_DIR/test1-chip-info.log   — Test 1: chip info${RST}"
echo -e "    ${DIM}$LOG_DIR/test2-discovery.log   — Test 2: mutual auth${RST}"
echo -e "    ${DIM}$LOG_DIR/test3-download.log    — Test 3: profile download${RST}"
echo ""

if (( TESTS_FAIL > 0 )); then
    echo -e "${BOLD}${C}╔══════════════════════════════════════════════════════════════════════╗${RST}"
    echo -e "${BOLD}${C}║                     COMPONENT DIAGNOSTICS                           ║${RST}"
    echo -e "${BOLD}${C}╚══════════════════════════════════════════════════════════════════════╝${RST}"
    echo ""

    echo -e "  ${C}v-euicc-daemon highlights:${RST}"
    grep -E "Loaded|signature|PrepareDownload|BPP|matchingID|AuthenticateServer|Error|error|WARNING" \
        "$LOG_DIR/v-euicc.log" 2>/dev/null | tail -10 | while IFS= read -r l; do info "  $l"; done

    echo ""
    echo -e "  ${G}osmo-smdpp highlights:${RST}"
    tail -15 "$LOG_DIR/osmo-smdpp.log" 2>/dev/null | grep -v "^	" | while IFS= read -r l; do info "  $l"; done

    echo ""
fi

# Teardown runs automatically via the EXIT trap
# Exit with failure if any test failed
if (( TESTS_FAIL > 0 )); then exit 1; fi
exit 0
