import socket
import os
import subprocess
import time
import signal
import sys

def find_free_port():
    """Find a free port on the system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def kill_existing_processes():
    """Kill any existing app.py processes."""
    try:
        os.system("pkill -f 'python app.py' || true")
        print("Killed any existing app.py processes")
        time.sleep(1)  # Give processes time to terminate
    except Exception as e:
        print(f"Error killing processes: {e}")

def start_server():
    """Start the server on a free port."""
    # Kill any existing processes
    kill_existing_processes()
    
    # Find a free port
    port = find_free_port()
    print(f"Starting server on port {port}")
    
    # Get the path to app.py in the parent directory
    app_path = os.path.join(os.path.dirname(os.getcwd()), 'app.py')
    print(f"Using app.py at: {app_path}")
    
    # Modify the app.py file to use this port
    with open(app_path, 'r') as f:
        content = f.read()
    
    # Replace the port in the app.py file
    import re
    new_content = re.sub(r'app\.run\(debug=True, port=\d+\)', f'app.run(debug=True, port={port})', content)
    
    # If no port is specified, add it
    if 'app.run(debug=True)' in content:
        new_content = content.replace('app.run(debug=True)', f'app.run(debug=True, port={port})')
    
    with open(app_path, 'w') as f:
        f.write(new_content)
    
    # Start the server
    try:
        print(f"Server will be available at: http://localhost:{port}")
        print(f"Press Ctrl+C to stop the server")
        # Change to the parent directory before running app.py
        os.chdir(os.path.dirname(os.getcwd()))
        subprocess.run(['python3', 'app.py'], check=True)
    except KeyboardInterrupt:
        print("Server stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")

if __name__ == "__main__":
    try:
        # Change to the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        print(f"Working directory: {os.getcwd()}")
        
        start_server()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        sys.exit(0)
