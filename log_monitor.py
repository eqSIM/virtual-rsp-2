#!/usr/bin/env python3
"""
Real-time colored log monitor for Virtual RSP
Monitors multiple log files and displays them with distinct colors for each component
"""

import sys
import time
import select
import os
from pathlib import Path
from typing import Dict, TextIO, Tuple

# Import our logging colors
sys.path.insert(0, '.')
from vrsp_logging import LogColors

class LogMonitor:
    def __init__(self):
        self.log_files: Dict[str, Tuple[TextIO, str, str]] = {}
        self.last_positions: Dict[str, int] = {}

    def add_log_file(self, name: str, path: str, color: str):
        """Add a log file to monitor"""
        try:
            # Create the file if it doesn't exist
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    f.write("")  # Create empty file

            file_obj = open(path, 'r', encoding='utf-8', errors='replace')
            # Seek to end of file
            file_obj.seek(0, 2)
            self.last_positions[name] = file_obj.tell()
            self.log_files[name] = (file_obj, color, path)
            print(f"{LogColors.DIM}[{time.strftime('%H:%M:%S')}] {color}monitor{LogColors.RESET} INFO     [monitor] Monitoring {name}: {path}{LogColors.RESET}")
        except Exception as e:
            print(f"{LogColors.DIM}[{time.strftime('%H:%M:%S')}] {LogColors.ERROR}monitor{LogColors.RESET} ERROR    [monitor] Failed to open {path}: {e}{LogColors.RESET}")

    def monitor_logs(self):
        """Monitor all log files and display new lines with colors"""
        print(f"{LogColors.BOLD}{LogColors.CYAN}Virtual RSP Log Monitor Started{LogColors.RESET}")
        print(f"{LogColors.DIM}Components: v-euicc({LogColors.CYAN}cyan{LogColors.DIM}), osmo-smdpp({LogColors.GREEN}green{LogColors.DIM}), lpac({LogColors.YELLOW}yellow{LogColors.DIM}), nginx({LogColors.MAGENTA}magenta{LogColors.DIM}), test({LogColors.BLUE}blue{LogColors.DIM}){LogColors.RESET}")
        print(f"{LogColors.DIM}Press Ctrl+C to stop monitoring{LogColors.RESET}")
        print()

        try:
            while True:
                # Check for new content in all files
                for name, (file_obj, color, path) in self.log_files.items():
                    try:
                        # Check if file still exists
                        if not os.path.exists(path):
                            continue

                        # Get current file size
                        current_pos = file_obj.tell()

                        # If file was truncated, reset position
                        if current_pos < self.last_positions.get(name, 0):
                            self.last_positions[name] = 0
                            file_obj.seek(0)

                        # Read new lines
                        lines = file_obj.readlines()
                        if lines:
                            for line in lines:
                                line = line.rstrip()
                                if line.strip():  # Skip empty lines
                                    # Color the component name if it matches our known components
                                    colored_line = self._colorize_line(line, color)
                                    print(colored_line)

                            # Update position
                            self.last_positions[name] = file_obj.tell()

                    except Exception as e:
                        print(f"{LogColors.DIM}[{time.strftime('%H:%M:%S')}] {LogColors.ERROR}monitor{LogColors.RESET} ERROR    [monitor] Error reading {name}: {e}{LogColors.RESET}")

                # Sleep briefly to avoid high CPU usage
                time.sleep(0.1)

        except KeyboardInterrupt:
            print(f"\n{LogColors.BOLD}{LogColors.CYAN}Log monitoring stopped{LogColors.RESET}")
        finally:
            self.cleanup()

    def _colorize_line(self, line: str, default_color: str) -> str:
        """Colorize a log line based on its content"""
        # If the line already has our logging format, keep its colors
        if '\033[' in line and ']' in line and any(comp in line for comp in ['v-euicc', 'osmo-smdpp', 'lpac', 'nginx', 'test']):
            return line

        # Otherwise, color the entire line with the component's color
        return f"{default_color}{line}{LogColors.RESET}"

    def cleanup(self):
        """Close all file handles"""
        for name, (file_obj, _, _) in self.log_files.items():
            try:
                file_obj.close()
            except:
                pass
        self.log_files.clear()

def main():
    monitor = LogMonitor()

    # Add log files to monitor
    monitor.add_log_file("v-euicc", "/tmp/v-euicc-test-all.log", LogColors.CYAN)
    monitor.add_log_file("osmo-smdpp", "/tmp/osmo-smdpp-test.log", LogColors.GREEN)
    monitor.add_log_file("lpac-discovery", "/tmp/test1-discovery.log", LogColors.YELLOW)
    monitor.add_log_file("lpac-download", "/tmp/test2-download.log", LogColors.YELLOW)
    monitor.add_log_file("nginx", "/tmp/nginx-test.log", LogColors.MAGENTA)

    # Start monitoring
    monitor.monitor_logs()

if __name__ == "__main__":
    main()
