#!/usr/bin/env python3
"""
DispatchMail Startup Script
This script starts all DispatchMail services (API + frontend) in the background.
"""

import os
import sys
import time
import signal
import subprocess
import threading
from pathlib import Path
from datetime import datetime

# Global list to track all processes
processes = []
log_files = []

def signal_handler(signum, frame):
    """Handle Ctrl+C by terminating all processes."""
    print("\n🛑 Shutting down dMail services...")
    for process in processes:
        if process.poll() is None:  # Process is still running
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    
    # Close log files
    for log_file in log_files:
        if not log_file.closed:
            log_file.close()
    
    print("✅ All services stopped")
    print("📝 Logs saved to:")
    for log_file in log_files:
        print(f"   - {log_file.name}")
    sys.exit(0)

def log_output(process, log_file, service_name):
    """Log output from a process to a file."""
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            
            # Add timestamp and write to log file
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{timestamp}] {line.rstrip()}\n"
            log_file.write(log_line)
            log_file.flush()
            
            # Show important messages in terminal
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['error', 'failed', 'exception', 'traceback']):
                print(f"🔴 {service_name}: {line.rstrip()}")
            elif any(keyword in line_lower for keyword in ['started', 'listening', 'running']):
                print(f"🟢 {service_name}: {line.rstrip()}")
    except Exception as e:
        print(f"❌ Error logging {service_name}: {e}")

def start_api():
    """Start the web API service."""
    print("🌐 Starting web API...")
    api_dir = Path("web-app")
    if not api_dir.exists():
        print("❌ web-app directory not found")
        return None
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    try:
        # Create log file
        log_file = open(logs_dir / "api.log", "w")
        log_files.append(log_file)
        
        process = subprocess.Popen(
            [sys.executable, "api/api.py"],
            cwd=api_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        processes.append(process)
        
        # Start logging thread
        log_thread = threading.Thread(target=log_output, args=(process, log_file, "API"))
        log_thread.start()
        
        time.sleep(2)  # Give it time to start
        
        if process.poll() is None:
            print("✅ Web API started on http://localhost:5000")
            print(f"📝 API logs: {log_file.name}")
            return process
        else:
            print("❌ Web API failed to start")
            return None
    except Exception as e:
        print(f"❌ Failed to start web API: {e}")
        return None

def start_frontend():
    """Start the frontend development server."""
    print("🎨 Starting frontend...")
    frontend_dir = Path("web-app")
    if not frontend_dir.exists():
        print("❌ web-app directory not found")
        return None
    
    # Check if package.json exists
    if not (frontend_dir / "package.json").exists():
        print("❌ package.json not found. Run 'npm install' first.")
        return None
    
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    try:
        # Create log file
        log_file = open(logs_dir / "frontend.log", "w")
        log_files.append(log_file)
        
        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        processes.append(process)
        
        # Start logging thread
        log_thread = threading.Thread(target=log_output, args=(process, log_file, "Frontend"))
        log_thread.daemon = True
        log_thread.start()
        
        time.sleep(3)  # Give it time to start
        
        if process.poll() is None:
            print("✅ Frontend started on http://localhost:5173")
            print(f"📝 Frontend logs: {log_file.name}")
            return process
        else:
            print("❌ Frontend failed to start")
            return None
    except Exception as e:
        print(f"❌ Failed to start frontend: {e}")
        return None

def check_prerequisites():
    """Check if all prerequisites are met."""
    print("🔍 Checking prerequisites...")
    
    # Check if credentials.py exists
    credentials_file = Path("web-app/api/credentials.py")
    if not credentials_file.exists():
        print("❌ Configuration file missing: web-app/api/credentials.py")
        print("   Run 'python setup.py' to create it")
        return False
    
    # Check if database.py exists
    if not Path("database.py").exists():
        print("❌ Database module missing: database.py")
        return False
    
    # Check if web-app directory exists
    if not Path("web-app").exists():
        print("❌ Web app directory missing: web-app")
        return False
    
    print("✅ Prerequisites check passed")
    return True

def main():
    """Main function to start all services."""
    print("🚀 Starting dMail Services")
    print("=========================")
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start all services
    api_process = start_api()
    frontend_process = start_frontend()
    
    # Check if all services started successfully
    failed_services = []
    if not api_process:
        failed_services.append("Web API")
    if not frontend_process:
        failed_services.append("Frontend")
    
    if failed_services:
        print(f"\n❌ Failed to start: {', '.join(failed_services)}")
        print("Check the logs above for error details")
        signal_handler(None, None)
        sys.exit(1)
    
    print("\n✅ All services started successfully!")
    print("📱 Web interface: http://localhost:5173")
    print("🔗 API endpoint: http://localhost:5000")
    print("\n📝 Logs are being saved to:")
    for log_file in log_files:
        print(f"   - {log_file.name}")
    print("\n💡 To view logs in real-time:")
    print("   tail -f logs/api.log")
    print("   tail -f logs/frontend.log")
    print("\nPress Ctrl+C to stop all services")
    
    # Monitor processes
    try:
        while True:
            time.sleep(1)
            
            # Check if any process has died
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    service_names = ["Web API", "Frontend"]
                    print(f"\n❌ {service_names[i]} has stopped unexpectedly")
                    print(f"   Check logs/{['api', 'frontend'][i]}.log for details")
                    signal_handler(None, None)
                    sys.exit(1)
                    
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main() 