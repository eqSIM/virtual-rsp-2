"""
Process Manager - Subprocess control for v-euicc, SM-DP+, and nginx
"""

import subprocess
import signal
import os
import time
from typing import Optional, Dict
from pathlib import Path


class ProcessManager:
    """
    Manages backend processes (v-euicc-daemon, osmo-smdpp, nginx).
    Handles starting, stopping, and monitoring process health.
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.processes: Dict[str, subprocess.Popen] = {}
        self.log_files: Dict[str, str] = {}
    
    def is_running(self, service_name: str) -> bool:
        """Check if a service is currently running"""
        # Special handling for nginx which forks into daemon
        if service_name == 'nginx':
            result = subprocess.run(['pgrep', '-f', 'nginx.*nginx-smdpp.conf'],
                                   capture_output=True, text=True)
            return result.returncode == 0
        
        if service_name not in self.processes:
            return False
        
        proc = self.processes[service_name]
        return proc.poll() is None
    
    def start_veuicc(self, port: int = 8765) -> tuple[bool, str]:
        """
        Start v-euicc-daemon on specified port.
        
        Returns: (success, message)
        """
        if self.is_running('veuicc'):
            return False, "v-euicc is already running"
        
        # Kill any existing process on the port
        try:
            subprocess.run(['lsof', '-ti', f':{port}'], 
                          capture_output=True, check=False)
            subprocess.run(['kill', '-9', f'`lsof -ti :{port}`'],
                          shell=True, check=False)
            time.sleep(1)
        except:
            pass
        
        veuicc_bin = self.project_root / "build/v-euicc/v-euicc-daemon"
        log_file = self.project_root / "data/veuicc.log"
        
        if not veuicc_bin.exists():
            return False, f"v-euicc binary not found: {veuicc_bin}"
        
        try:
            log_f = open(log_file, 'w')
            proc = subprocess.Popen(
                [str(veuicc_bin), str(port)],
                stdout=log_f,
                stderr=subprocess.STDOUT,
                cwd=str(self.project_root)
            )
            
            # Wait a moment to check it didn't immediately crash
            time.sleep(1)
            if proc.poll() is not None:
                return False, "v-euicc crashed on startup"
            
            self.processes['veuicc'] = proc
            self.log_files['veuicc'] = str(log_file)
            return True, f"v-euicc started on port {port}"
            
        except Exception as e:
            return False, f"Failed to start v-euicc: {e}"
    
    def stop_veuicc(self) -> tuple[bool, str]:
        """Stop v-euicc-daemon"""
        if not self.is_running('veuicc'):
            return False, "v-euicc is not running"
        
        try:
            proc = self.processes['veuicc']
            proc.terminate()
            
            # Wait up to 5 seconds for graceful shutdown
            for _ in range(50):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            else:
                # Force kill if still running
                proc.kill()
            
            del self.processes['veuicc']
            return True, "v-euicc stopped"
            
        except Exception as e:
            return False, f"Failed to stop v-euicc: {e}"
    
    def start_smdp(self, host: str = "127.0.0.1", port: int = 8000) -> tuple[bool, str]:
        """
        Start osmo-smdpp.py (SM-DP+ server).
        
        Returns: (success, message)
        """
        if self.is_running('smdp'):
            return False, "SM-DP+ is already running"
        
        # Kill any existing process on the port
        try:
            subprocess.run(['lsof', '-ti', f':{port}'],
                          capture_output=True, check=False)
            subprocess.run(['kill', '-9', f'`lsof -ti :{port}`'],
                          shell=True, check=False)
            time.sleep(1)
        except:
            pass
        
        smdp_script = self.project_root / "pysim/osmo-smdpp.py"
        log_file = self.project_root / "data/smdp.log"
        
        if not smdp_script.exists():
            return False, f"SM-DP+ script not found: {smdp_script}"
        
        try:
            log_f = open(log_file, 'w')
            proc = subprocess.Popen(
                ['python3', str(smdp_script), '-H', host, '-p', str(port), 
                 '--nossl', '-c', 'generated'],
                stdout=log_f,
                stderr=subprocess.STDOUT,
                cwd=str(self.project_root / "pysim")
            )
            
            # Wait a moment
            time.sleep(2)
            if proc.poll() is not None:
                return False, "SM-DP+ crashed on startup"
            
            self.processes['smdp'] = proc
            self.log_files['smdp'] = str(log_file)
            return True, f"SM-DP+ started on {host}:{port}"
            
        except Exception as e:
            return False, f"Failed to start SM-DP+: {e}"
    
    def stop_smdp(self) -> tuple[bool, str]:
        """Stop SM-DP+ server"""
        if not self.is_running('smdp'):
            return False, "SM-DP+ is not running"
        
        try:
            proc = self.processes['smdp']
            proc.terminate()
            
            for _ in range(50):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
            else:
                proc.kill()
            
            del self.processes['smdp']
            return True, "SM-DP+ stopped"
            
        except Exception as e:
            return False, f"Failed to stop SM-DP+: {e}"
    
    def start_nginx(self, https_port: int = 8443) -> tuple[bool, str]:
        """
        Start nginx reverse proxy for HTTPS.
        
        Returns: (success, message)
        """
        if self.is_running('nginx'):
            return False, "nginx is already running"
        
        # Kill any existing nginx
        try:
            subprocess.run(['pkill', '-9', 'nginx'], check=False)
            time.sleep(1)
        except:
            pass
        
        nginx_conf = self.project_root / "pysim/nginx-smdpp.conf"
        log_file = self.project_root / "data/nginx.log"
        
        if not nginx_conf.exists():
            return False, f"nginx config not found: {nginx_conf}"
        
        try:
            log_f = open(log_file, 'w')
            proc = subprocess.Popen(
                ['nginx', '-c', str(nginx_conf), '-p', str(self.project_root / "pysim")],
                stdout=log_f,
                stderr=subprocess.STDOUT,
                cwd=str(self.project_root / "pysim")
            )
            
            time.sleep(1)
            if proc.poll() is not None:
                return False, "nginx crashed on startup"
            
            self.processes['nginx'] = proc
            self.log_files['nginx'] = str(log_file)
            return True, f"nginx started (HTTPS port {https_port})"
            
        except Exception as e:
            return False, f"Failed to start nginx: {e}"
    
    def stop_nginx(self) -> tuple[bool, str]:
        """Stop nginx"""
        if not self.is_running('nginx'):
            return False, "nginx is not running"
        
        try:
            # nginx needs to be stopped with signal
            subprocess.run(['pkill', '-15', 'nginx'], check=False)
            
            if 'nginx' in self.processes:
                del self.processes['nginx']
            
            return True, "nginx stopped"
            
        except Exception as e:
            return False, f"Failed to stop nginx: {e}"
    
    def get_log_file(self, service_name: str) -> Optional[str]:
        """Get log file path for a service"""
        return self.log_files.get(service_name)
    
    def stop_all(self):
        """Stop all managed processes"""
        for service in ['nginx', 'smdp', 'veuicc']:
            if service == 'nginx':
                self.stop_nginx()
            elif service == 'smdp':
                self.stop_smdp()
            elif service == 'veuicc':
                self.stop_veuicc()

