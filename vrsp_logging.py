#!/usr/bin/env python3
"""
Comprehensive Colored Logging Service for Virtual RSP
Provides consistent logging across all Python components with distinct colors
"""

import sys
import time
import os
from typing import Optional

# ANSI Color Codes
class LogColors:
    RESET = "\033[0m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Component-specific colors
    V_EUICC = CYAN
    OSMO_SMDPP = GREEN
    LPAC = YELLOW
    NGINX = MAGENTA
    TEST = BLUE
    ERROR = RED
    SUCCESS = GREEN + BOLD

# Component names
class LogComponents:
    V_EUICC = "v-euicc"
    OSMO_SMDPP = "osmo-smdpp"
    LPAC = "lpac"
    NGINX = "nginx"
    TEST = "test"

class LogLevel:
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
    CRITICAL = 4

# Global log level
_current_log_level = LogLevel.INFO

def set_log_level(level: int):
    """Set the global log level"""
    global _current_log_level
    _current_log_level = level

def _get_timestamp() -> str:
    """Get current timestamp as HH:MM:SS"""
    return time.strftime("%H:%M:%S")

def _get_pid() -> int:
    """Get current process ID"""
    return os.getpid()

def _log_message(level: int, component: str, color: str, level_str: str, message: str, *args):
    """Internal logging function"""
    if level < _current_log_level:
        return

    timestamp = _get_timestamp()
    pid = _get_pid()

    # Format the message
    if args:
        try:
            formatted_message = message % args
        except (TypeError, ValueError):
            formatted_message = message + " " + str(args)
    else:
        formatted_message = message

    # Print with colors
    print(f"{LogColors.DIM}[{timestamp}] {color}{component:<12}{LogColors.RESET} {level_str:<8} [{pid}] {formatted_message}{LogColors.RESET}",
          file=sys.stderr)

# Convenience functions for different log levels
def debug(component: str, color: str, message: str, *args):
    """Log debug message"""
    _log_message(LogLevel.DEBUG, component, color, "DEBUG", message, *args)

def info(component: str, color: str, message: str, *args):
    """Log info message"""
    _log_message(LogLevel.INFO, component, color, "INFO", message, *args)

def warn(component: str, color: str, message: str, *args):
    """Log warning message"""
    _log_message(LogLevel.WARN, component, color, "WARN", message, *args)

def error(component: str, color: str, message: str, *args):
    """Log error message"""
    _log_message(LogLevel.ERROR, component, color, "ERROR", message, *args)

def critical(component: str, color: str, message: str, *args):
    """Log critical message"""
    _log_message(LogLevel.CRITICAL, component, color, "CRITICAL", message, *args)

# Hex dump utility
def hex_dump(component: str, color: str, prefix: str, data: bytes, max_len: Optional[int] = None):
    """Log hex dump of binary data"""
    if LogLevel.DEBUG < _current_log_level:
        return

    if max_len and len(data) > max_len:
        display_data = data[:max_len]
        suffix = f" ... ({len(data)} total)"
    else:
        display_data = data
        suffix = ""

    timestamp = _get_timestamp()
    pid = _get_pid()

    print(f"{LogColors.DIM}[{timestamp}] {color}{component:<12}{LogColors.RESET} DEBUG    [{pid}] {prefix} ({len(data)} bytes):{LogColors.RESET}",
          file=sys.stderr)

    # Print hex dump
    for i in range(0, len(display_data), 16):
        chunk = display_data[i:i+16]
        hex_part = ' '.join('.2x' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)

        print(f"{LogColors.DIM}[{timestamp}] {color}{component:<12}{LogColors.RESET} DEBUG    [{pid}]   {hex_part:<48} {ascii_part}{LogColors.RESET}",
              file=sys.stderr)

    if suffix:
        print(f"{LogColors.DIM}[{timestamp}] {color}{component:<12}{LogColors.RESET} DEBUG    [{pid}]   {suffix}{LogColors.RESET}",
              file=sys.stderr)

# Component-specific logging functions
class VEuiccLogger:
    @staticmethod
    def debug(message: str, *args):
        debug(LogComponents.V_EUICC, LogColors.V_EUICC, message, *args)

    @staticmethod
    def info(message: str, *args):
        info(LogComponents.V_EUICC, LogColors.V_EUICC, message, *args)

    @staticmethod
    def warn(message: str, *args):
        warn(LogComponents.V_EUICC, LogColors.V_EUICC, message, *args)

    @staticmethod
    def error(message: str, *args):
        error(LogComponents.V_EUICC, LogColors.V_EUICC, message, *args)

    @staticmethod
    def hex_dump(prefix: str, data: bytes, max_len: Optional[int] = None):
        hex_dump(LogComponents.V_EUICC, LogColors.V_EUICC, prefix, data, max_len)

class OsmoSmdppLogger:
    @staticmethod
    def debug(message: str, *args):
        debug(LogComponents.OSMO_SMDPP, LogColors.OSMO_SMDPP, message, *args)

    @staticmethod
    def info(message: str, *args):
        info(LogComponents.OSMO_SMDPP, LogColors.OSMO_SMDPP, message, *args)

    @staticmethod
    def warn(message: str, *args):
        warn(LogComponents.OSMO_SMDPP, LogColors.OSMO_SMDPP, message, *args)

    @staticmethod
    def error(message: str, *args):
        error(LogComponents.OSMO_SMDPP, LogColors.OSMO_SMDPP, message, *args)

    @staticmethod
    def hex_dump(prefix: str, data: bytes, max_len: Optional[int] = None):
        hex_dump(LogComponents.OSMO_SMDPP, LogColors.OSMO_SMDPP, prefix, data, max_len)

class LpacLogger:
    @staticmethod
    def debug(message: str, *args):
        debug(LogComponents.LPAC, LogColors.LPAC, message, *args)

    @staticmethod
    def info(message: str, *args):
        info(LogComponents.LPAC, LogColors.LPAC, message, *args)

    @staticmethod
    def warn(message: str, *args):
        warn(LogComponents.LPAC, LogColors.LPAC, message, *args)

    @staticmethod
    def error(message: str, *args):
        error(LogComponents.LPAC, LogColors.LPAC, message, *args)

    @staticmethod
    def hex_dump(prefix: str, data: bytes, max_len: Optional[int] = None):
        hex_dump(LogComponents.LPAC, LogColors.LPAC, prefix, data, max_len)

class TestLogger:
    @staticmethod
    def debug(message: str, *args):
        debug(LogComponents.TEST, LogColors.TEST, message, *args)

    @staticmethod
    def info(message: str, *args):
        info(LogComponents.TEST, LogColors.TEST, message, *args)

    @staticmethod
    def warn(message: str, *args):
        warn(LogComponents.TEST, LogColors.TEST, message, *args)

    @staticmethod
    def error(message: str, *args):
        error(LogComponents.TEST, LogColors.TEST, message, *args)

    @staticmethod
    def success(message: str, *args):
        info(LogComponents.TEST, LogColors.SUCCESS, message, *args)

# Initialize with INFO level by default
set_log_level(LogLevel.INFO)
