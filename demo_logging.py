#!/usr/bin/env python3
"""
Demo script showcasing the Virtual RSP colored logging system
"""

import time
import sys
sys.path.insert(0, '.')

from vrsp_logging import (
    VEuiccLogger, OsmoSmdppLogger, LpacLogger, TestLogger,
    LogColors, set_log_level, LogLevel
)

def demo_colored_logging():
    """Demonstrate the colored logging system"""
    print(f"{LogColors.BOLD}{LogColors.CYAN}Virtual RSP Colored Logging Demo{LogColors.RESET}")
    print(f"{LogColors.DIM}This demo shows how each component gets distinct colors for easy identification{LogColors.RESET}")
    print()

    # Set to INFO level to show all messages
    set_log_level(LogLevel.INFO)

    # Demo messages from different components
    print("🚀 Starting component demonstrations...\n")

    # v-euicc messages (cyan)
    VEuiccLogger.info("Virtual eUICC daemon started on port 8765")
    VEuiccLogger.info("Loaded eUICC certificate: 513 bytes")
    VEuiccLogger.info("Loaded EUM certificate: 636 bytes")
    VEuiccLogger.info("Loaded eUICC private key (P-256)")
    VEuiccLogger.info("AuthenticateServer: Real ECDSA signature generated (64 bytes)")
    time.sleep(0.5)

    # osmo-smdpp messages (green)
    OsmoSmdppLogger.info("osmo-smdpp starting on 127.0.0.1:8000 (SSL: disabled)")
    OsmoSmdppLogger.info("Loaded SM-DP+ certificates from generated/")
    OsmoSmdppLogger.info("Certificate chain verification successful")
    OsmoSmdppLogger.warn("No active sessions found, starting fresh")
    time.sleep(0.5)

    # lpac messages (yellow)
    LpacLogger.info("LPA client initialized with socket APDU interface")
    LpacLogger.info("Connecting to SM-DP+ at testsmdpplus1.example.com:8443")
    LpacLogger.info("Profile discovery initiated")
    LpacLogger.info("es11_authenticate_client: Mutual authentication successful")
    LpacLogger.error("Profile download failed: HTTP 500 from SM-DP+")
    time.sleep(0.5)

    # Test framework messages (blue)
    TestLogger.info("Test suite initialization complete")
    TestLogger.info("Services started: v-euicc(PID 1234), osmo-smdpp(PID 1235), nginx(PID 1236)")
    TestLogger.success("Mutual authentication test PASSED")
    TestLogger.error("Profile download test FAILED - ASN.1 decode error")
    TestLogger.info("Generating test report...")

    print()
    print(f"{LogColors.BOLD}Color Legend:{LogColors.RESET}")
    print(f"  {LogColors.CYAN}Cyan{LogColors.RESET}     - v-euicc daemon (C code)")
    print(f"  {LogColors.GREEN}Green{LogColors.RESET}    - osmo-smdpp server (Python)")
    print(f"  {LogColors.YELLOW}Yellow{LogColors.RESET}   - lpac client (C code)")
    print(f"  {LogColors.BLUE}Blue{LogColors.RESET}      - Test framework (Shell/Python)")
    print(f"  {LogColors.MAGENTA}Magenta{LogColors.RESET}  - nginx web server")
    print(f"  {LogColors.RED}Red{LogColors.RESET}       - Error messages")
    print()
    print(f"{LogColors.BOLD}Usage:{LogColors.RESET}")
    print("  Run './test-all.sh' for complete test with real-time colored logs")
    print("  Run './log_monitor.py' to monitor logs during development")
    print("  Each component's logs are automatically color-coded for clarity")

if __name__ == "__main__":
    demo_colored_logging()
