import xmlrpc.client
import xmlrpc.server
import sys
import os
import argparse
import socket
import readline
import signal
import time
from threading import Thread, Lock

class P2PFileSystem:
    def __init__(self, port=8000, key=None):
        self.port = port
        self.nodes = {}
        self.node_counter = 0
        self.used_ids = set()  # Add a set for used IDs
        self.file_manager = FileManager()
        self.nodes_lock = Lock()
        self.security_key = key
        self.local_node_key = None  # Store the local node's key
        
    def get_next_available_id(self):
        # Find the smallest available ID
        used_ids = set(self.used_ids)
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        return next_id

    def register_node(self, ip_address, port, hostname, security_key=None):
        # Security key verification
        if self.security_key and security_key != self.security_key:
            return {'error': 'Security key verification failed'}
            
        # Perform a cleanup first to reclaim IDs of disconnected nodes
        print(f"Registering node: {ip_address}:{port} with hostname: {hostname}")
        self.cleanup_inactive_nodes()
        print(f"Registering node: {ip_address}:{port} with hostname: {hostname}")
            
        # Use IP:port as the node identifier
        node_key = f"{ip_address}:{port}"
        
        with self.nodes_lock:
            # Check if node already exists, just update timestamp if it does
            if node_key in self.nodes:
                self.nodes[node_key]['last_active'] = time.time()
                return {'id': self.nodes[node_key]['id']}
            
            # Check if hostname is already in use
            for node_info in self.nodes.values():
                if node_info['hostname'] == hostname:
                    return {'error': f'Hostname {hostname} is already in use'}
                
            # Check if hostname starts with 'id'
            if hostname.lower().startswith('id'):
                return {'error': f'Hostname cannot start with "id"'}
            
            # Get the next available ID
            next_id = self.get_next_available_id()
            self.used_ids.add(next_id)  # Add ID to the used set
            self.node_counter = max(self.node_counter, next_id)  # Update counter
            
            self.nodes[node_key] = {
                'id': next_id,
                'hostname': hostname,
                'ip': ip_address,
                'port': port,
                'last_active': time.time()
            }
            
            # If this is a local node, store its key
            if ip_address == '127.0.0.1' and port == self.port:
                self.local_node_key = node_key
                
            return {'id': next_id}

    def heartbeat(self, ip_address, port):
        """Update the last active timestamp for a node"""
        node_key = f"{ip_address}:{port}"
        with self.nodes_lock:
            if node_key in self.nodes:
                self.nodes[node_key]['last_active'] = time.time()
                return {'status': 'success'}
            return {'status': 'error', 'message': 'Node not found'}

    def unregister_node(self, ip_address, port):
        node_key = f"{ip_address}:{port}"
        with self.nodes_lock:
            if node_key in self.nodes:
                node_id = self.nodes[node_key]['id']
                self.used_ids.remove(node_id)  # Remove ID from the used set
                del self.nodes[node_key]
                return {'status': 'success', 'message': f'Node {node_key} has been removed'}
            return {'status': 'error', 'message': f'Node {node_key} does not exist'}

    def cleanup_inactive_nodes(self, timeout=120):  # Increased timeout to 120 seconds
        current_time = time.time()
        inactive_nodes = []
        
        with self.nodes_lock:
            for node_key, node_info in list(self.nodes.items()):
                # Don't clean up the local node
                if node_key == self.local_node_key:
                    continue
                    
                if (current_time - node_info.get('last_active', 0)) > timeout:
                    inactive_nodes.append(node_key)
                    self.used_ids.remove(node_info['id'])  # Remove ID from the used set
                    del self.nodes[node_key]
        
        return inactive_nodes

    def start_server(self):
        server = xmlrpc.server.SimpleXMLRPCServer(('0.0.0.0', self.port),
                                                 allow_none=True)
        server.register_instance(self)
        # Register binary transfer methods
        server.register_function(self.file_manager.binary_read, 'binary_read')
        server.register_function(self.file_manager.binary_write, 'binary_write')
        # Register heartbeat method explicitly
        server.register_function(self.heartbeat, 'heartbeat')
        server.register_function(self.unregister_node, 'unregister_node')
        server.register_function(self.get_nodes, 'get_nodes')
        server.register_function(self.get_node_by_hostname, 'get_node_by_hostname')
        server.register_function(self.register_node, 'register_node')
        server.register_function(self.get_help, 'get_help')
        server.register_function(self.route_command, 'route_command')
        print(f"P2P node started on port {self.port}...")
        
        # Start a thread for self-heartbeat to keep the local node active
        self_heartbeat_thread = Thread(target=self.self_heartbeat, daemon=True)
        self_heartbeat_thread.start()
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServer shutting down...")
            
    def self_heartbeat(self):
        """Send heartbeat for the local node"""
        while True:
            try:
                if self.local_node_key:
                    with self.nodes_lock:
                        if self.local_node_key in self.nodes:
                            self.nodes[self.local_node_key]['last_active'] = time.time()
                time.sleep(10)  # Update every 10 seconds
            except Exception:
                time.sleep(5)

    def route_command(self, node_id, command, *args):
        # Find node information
        target_node = None
        
        with self.nodes_lock:
            for node_key, node_info in self.nodes.items():
                if node_info['id'] == node_id:
                    target_node = node_info.copy()
                    break
                    
        if not target_node:
            return f"Error: Node {node_id} does not exist"
        
        # Check if it is a local node
        if target_node['ip'] == '127.0.0.1' and target_node['port'] == self.port:
            # Local node, execute the command directly
            return getattr(self.file_manager, command)(*args)
        else:
            # Remote node, forward the request
            try:
                # Create a proxy using the correct IP and port of the node
                proxy = xmlrpc.client.ServerProxy(f"http://{target_node['ip']}:{target_node['port']}")
                # Directly call the file management command on the remote node
                return getattr(proxy, command)(*args)
            except Exception as e:
                return f"Error: Failed to connect to node {node_id} - {str(e)}"

    def get_nodes(self):
        with self.nodes_lock:
            print(f"Current nodes: {self.nodes}")
            return {ip: node_info for ip, node_info in self.nodes.items()}
    
    def get_node_by_hostname(self, hostname):
        with self.nodes_lock:
            for node_key, node_info in self.nodes.items():
                if node_info['hostname'] == hostname:
                    return node_info
            return None
            
    def get_help(self):
        help_text = """
P2P File System Command Help:

Basic Commands:
  client                - List all connected nodes
  exit                  - Exit the client
  help                  - Display this help message

File Operation Commands (requires node ID or hostname prefix):
  mkdir idNode:path        - Create a directory
  rm idNode:path           - Remove a file or directory
  touch idNode:path        - Create an empty file
  ls idNode:path           - List directory contents (with file type indicators)
  tree idNode:path         - Display directory structure in a tree format
  cat idNode:path          - Display file content
  echo idNode:path content - Write content to a file
  cp srcIdNode:path dstIdNode:path - Copy a file
  mv srcIdNode:path dstIdNode:path - Move a file

Examples:
  mkdir id1:/test       - Create /test directory on node 1
  ls id2:/              - List the root directory contents of node 2
  cp id1:/file.txt id3:/backup.txt - Copy file from node 1 to node 3
  
You can also use hostnames instead of IDs:
  mkdir hostname1:/test - Create /test directory on host 'hostname1'
  ls hostname2:/        - List the root directory contents of host 'hostname2'

Note: All path operations require a node ID or hostname prefix.
"""
        return help_text
        
    # Add file management methods, directly forwarding to FileManager
    def mkdir(self, path):
        return self.file_manager.mkdir(path)
        
    def rm(self, path):
        return self.file_manager.rm(path)
        
    def touch(self, path):
        return self.file_manager.touch(path)
        
    def ls(self, path="."):
        return self.file_manager.ls(path)
        
    def tree(self, path="."):
        return self.file_manager.tree(path)
        
    def cat(self, path):
        return self.file_manager.cat(path)
        
    def echo(self, path, content):
        return self.file_manager.echo(path, content)
        
    def cp(self, src_path, dst_path):
        return self.file_manager.cp(src_path, dst_path)
        
    def mv(self, src_path, dst_path):
        return self.file_manager.mv(src_path, dst_path)

class FileManager:
    def mkdir(self, path):
        try:
            os.makedirs(path, exist_ok=True)
            return f"Directory '{path}' created successfully"
        except Exception as e:
            return f"Error: Failed to create directory - {str(e)}"

    def rm(self, path):
        try:
            if os.path.isdir(path):
                os.rmdir(path)
                return f"Directory '{path}' removed successfully"
            elif os.path.isfile(path):
                os.remove(path)
                return f"File '{path}' removed successfully"
            else:
                return f"Error: '{path}' does not exist"
        except Exception as e:
            return f"Error: Removal failed - {str(e)}"

    def touch(self, path):
        try:
            with open(path, 'a'):
                os.utime(path, None)
            return f"File '{path}' created successfully"
        except Exception as e:
            return f"Error: Failed to create file - {str(e)}"

    def ls(self, path="."):
        try:
            entries = os.listdir(path)
            result = []
            for entry in entries:
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    entry = entry + "/"
                result.append(entry)
            return '\n'.join(result)
        except Exception as e:
            return f"Error: Failed to list directory - {str(e)}"

    def tree(self, path="."):
        try:
            result = []
            path = path.rstrip('/')
            base_name = os.path.basename(path) or path
            result.append(f"{base_name}/")
            
            for root, dirs, files in os.walk(path):
                rel_path = os.path.relpath(root, path)
                if rel_path == '.':
                    level = 0
                else:
                    level = rel_path.count(os.sep) + 1
                    
                indent = '│  ' * (level - 1) + '├─ ' if level > 0 else ''
                
                for i, d in enumerate(dirs):
                    if i == len(dirs) - 1 and not files:
                        result.append(f"{indent}└─ {d}/")
                    else:
                        result.append(f"{indent}├─ {d}/")
                        
                file_indent = '│  ' * level + '├─ '
                last_file_indent = '│  ' * level + '└─ '
                
                for i, f in enumerate(files):
                    if i == len(files) - 1:
                        result.append(f"{last_file_indent}{f}")
                    else:
                        result.append(f"{file_indent}{f}")
                        
            return '\n'.join(result)
        except Exception as e:
            return f"Error: Failed to generate directory tree - {str(e)}"

    def cat(self, path):
        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"Error: Failed to read file - {str(e)}"

    def echo(self, path, content):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            return f"Content written to '{path}'"
        except Exception as e:
            return f"Error: Failed to write to file - {str(e)}"

    def cp(self, src_path, dst_path):
        try:
            if os.path.isfile(src_path):
                # Ensure the target directory exists
                dst_dir = os.path.dirname(os.path.abspath(dst_path))
                os.makedirs(dst_dir, exist_ok=True)
                
                with open(src_path, 'rb') as src:
                    with open(dst_path, 'wb') as dst:
                        dst.write(src.read())
                return f"Copied '{src_path}' to '{dst_path}'"
            else:
                return f"Error: Source file '{src_path}' does not exist or is not a file"
        except Exception as e:
            return f"Error: Failed to copy file - {str(e)}"

    def mv(self, src_path, dst_path):
        try:
            if not os.path.exists(src_path):
                return f"Error: Source path '{src_path}' does not exist"
                
            # Ensure the target directory exists
            dst_dir = os.path.dirname(os.path.abspath(dst_path))
            os.makedirs(dst_dir, exist_ok=True)
            
            os.rename(src_path, dst_path)
            return f"Moved '{src_path}' to '{dst_path}'"
        except Exception as e:
            return f"Error: Failed to move file - {str(e)}"

    def binary_read(self, path):
        try:
            with open(path, 'rb') as f:
                return xmlrpc.client.Binary(f.read())
        except Exception as e:
            return f"Error: Failed to read file - {str(e)}"

    def binary_write(self, path, binary_data):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(binary_data.data)
            return f"File written to '{path}'"
        except Exception as e:
            return f"Error: Failed to write to file - {str(e)}"

class P2PClient:
    def __init__(self, server_address, port, hostname=None, key=None):
        # Parse server address and port
        if ':' in server_address:
            server_address, connect_port = server_address.split(':')
            connect_port = int(connect_port)
        else:
            connect_port = port
        
        self.server_address = server_address
        self.connect_port = connect_port
        self.server = xmlrpc.client.ServerProxy(f"http://{server_address}:{connect_port}", allow_none=True)
        self.port = port
        self.security_key = key
        
        # Get the local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Connect to an external address (no actual connection needed) to get the local IP
            s.connect((server_address, connect_port))
            self.local_ip = s.getsockname()[0]
        finally:
            s.close()
            
        # Prefer user-specified hostname, if not specified, use system hostname
        self.hostname = hostname or socket.gethostname()
        
        # Check if hostname starts with 'id'
        if self.hostname.lower().startswith('id'):
            print(f"Error: Hostname cannot start with 'id'")
            sys.exit(1)
        
        # Try to register multiple times if initial attempts fail
        retry_count = 0
        max_retries = 5
        while retry_count < max_retries:
            try:
                result = self.server.register_node(self.local_ip, self.port, self.hostname, self.security_key)
                if 'error' in result:
                    print(f"Error: {result['error']}")
                    if 'Hostname' in result['error'] and retry_count < max_retries - 1:
                        # Try with a different hostname
                        self.hostname = f"{self.hostname}-{retry_count + 1}"
                        print(f"Retrying with hostname: {self.hostname}")
                        retry_count += 1
                        continue
                    sys.exit(1)
                self.node_id = result['id']
                break
            except Exception as e:
                print(f"Connection error: {str(e)}")
                time.sleep(2)  # Wait before retry
                retry_count += 1
                if retry_count >= max_retries:
                    print("Maximum retry attempts reached. Exiting.")
                    sys.exit(1)
        
        # Initialize command history
        self.command_history = []
        self.setup_readline()
        
        # Create heartbeat thread
        self.running = True
        self.heartbeat_thread = Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def setup_readline(self):
        # Set up readline to support command history and editing features
        readline.parse_and_bind('"\\e[A": history-search-backward')  # Up arrow
        readline.parse_and_bind('"\\e[B": history-search-forward')   # Down arrow
        readline.parse_and_bind('"\\e[C": forward-char')             # Right arrow
        readline.parse_and_bind('"\\e[D": backward-char')            # Left arrow
        readline.parse_and_bind('"\\C-l": clear-screen')             # Ctrl+L clear screen
        
        # If the history file exists, load it
        histfile = os.path.expanduser('~/.p2p_history')
        try:
            readline.read_history_file(histfile)
            readline.set_history_length(1000)
        except FileNotFoundError:
            pass
            
        # Save history on exit
        import atexit
        atexit.register(readline.write_history_file, histfile)

    def heartbeat_loop(self):
        while self.running:
            try:
                self.server.heartbeat(self.local_ip, self.port)
                time.sleep(10)  # Send a heartbeat every 10 seconds
            except Exception as e:
                # Print error but continue trying
                print(f"\nHeartbeat failed: {str(e)}")
                print(f"{self.hostname}> ", end='', flush=True)
                time.sleep(5)  # Wait a bit before retrying after failure

    def parse_path(self, path_spec):
        """Parse the specified path format, supporting ID and hostname prefixes"""
        if ':' not in path_spec:
            print(f"Error: Path must include a node identifier, in the format 'idN:path' or 'hostname:path'")
            return None, None
            
        prefix, path = path_spec.split(':', 1)
        
        # Check if it is an ID format (id followed by digits)
        if prefix.lower().startswith('id') and prefix[2:].isdigit():
            node_id = int(prefix[2:])
            return node_id, path
            
        # Otherwise, consider it as a hostname
        try:
            node_info = self.server.get_node_by_hostname(prefix)
            if not node_info:
                print(f"Error: Could not find a node with hostname '{prefix}'")
                return None, None
            return node_info['id'], path
        except Exception as e:
            print(f"Error: An error occurred while parsing the path - {str(e)}")
            return None, None

    def run(self):
        # Block Ctrl+C
        original_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self.handle_interrupt)
        
        # Main loop
        while self.running:
            try:
                # Update command prompt to show hostname
                prompt = f"{self.hostname}> "
                cmd_input = input(prompt).strip()
                
                if not cmd_input:
                    continue
                    
                # Add to command history
                readline.add_history(cmd_input)
                
                cmd = cmd_input.split()
                action = cmd[0]
                
                if action == 'exit':
                    self.running = False
                    # Unregister node
                    try:
                        self.server.unregister_node(self.local_ip, self.port)
                    except Exception:
                        pass  # Ignore unregistration errors
                    break
                    
                elif action == 'help':
                    print(self.server.get_help())
                    continue
                    
                elif action == 'client':
                    nodes = self.server.get_nodes()
                    print("\nConnected Nodes List:")
                    print("-" * 60)
                    print(f"{'ID':<5} {'Hostname':<15} {'Address':<20} {'Port':<6}")
                    print("-" * 60)
                    for ip, node_info in nodes.items():
                        print(f"id{node_info['id']:<3} {node_info['hostname']:<15} {node_info['ip']:<20} {node_info['port']:<6}")
                    print("-" * 60)
                    continue

                if action in ['mkdir', 'rm', 'touch', 'ls', 'tree', 'cat']:
                    if len(cmd) != 2:
                        print(f"Usage: {action} NodeID:path")
                        print(f"Example: {action} id1:/home or {action} hostname:/home")
                        continue
                        
                    node_id, path = self.parse_path(cmd[1])
                    if node_id is None:
                        continue
                        
                    result = self.server.route_command(node_id, action, path)
                    print(result)
                elif action == 'echo':
                    if len(cmd) < 3:
                        print("Usage: echo NodeID:path content")
                        print("Example: echo id1:/file.txt file content or echo hostname:/file.txt file content")
                        continue
                    
                    node_id, path = self.parse_path(cmd[1])
                    if node_id is None:
                        continue
                    
                    # Get initial content
                    initial_content = ' '.join(cmd[2:])
                    
                    # Initialize buffer and console state
                    buffer = []
                    console = list(initial_content)
                    backtick_count = 0
                    in_multiline = False
                    i = 0
                    
                    while i < len(console):
                        if console[i] == '\\':
                            # Handle escape characters
                            if i + 1 < len(console):
                                buffer.append(console[i + 1])
                                i += 2
                                backtick_count = 0  # Reset backtick count
                            else:
                                buffer.append('\\')
                                i += 1
                        elif console[i] == '`':
                            backtick_count += 1
                            if backtick_count == 3:
                                # Enter or exit multiline mode
                                if not in_multiline:
                                    # Remove the last two backticks
                                    if len(buffer) >= 2:
                                        buffer = buffer[:-2]
                                    in_multiline = True
                                else:
                                    in_multiline = False
                                backtick_count = 0
                                i += 1
                            else:
                                if backtick_count < 3:
                                   buffer.append('`')
                                i += 1
                        else:
                            buffer.append(console[i])
                            backtick_count = 0  # Reset backtick count
                            i += 1
                    
                    # If in multiline mode, continue collecting input
                    if in_multiline:
                        while True:
                            try:
                                line = input()
                                console = list(line)
                                i = 0
                                line_buffer = []
                                backtick_count = 0
                                
                                while i < len(console):
                                    if console[i] == '\\':
                                        if i + 1 < len(console):
                                            line_buffer.append(console[i + 1])
                                            i += 2
                                            backtick_count = 0
                                        else:
                                            line_buffer.append('\\')
                                            i += 1
                                    elif console[i] == '`':
                                        backtick_count += 1
                                        if backtick_count == 3:
                                            in_multiline = False
                                            break
                                        else:
                                            line_buffer.append('`')
                                        i += 1
                                    else:
                                        line_buffer.append(console[i])
                                        backtick_count = 0
                                        i += 1
                                
                                if not in_multiline:
                                    # Do not include the ending triple backticks
                                    buffer.extend(['\n'] + line_buffer[:-2])
                                    break
                                else:
                                    buffer.extend(['\n'] + line_buffer)
                                    
                            except EOFError:
                                print("Input terminated.")
                                break
                    
                    final_content = ''.join(buffer)
                    
                    result = self.server.route_command(node_id, action, path, final_content)
                    print(result)
                elif action in ['cp', 'mv']:
                    if len(cmd) != 3:
                        print(f"Usage: {action} srcNodeID:srcPath dstNodeID:dstPath")
                        print(f"Example: {action} id1:/src.txt id2:/dst.txt or {action} hostname1:/src.txt hostname2:/dst.txt")
                        continue
                        
                    src_node, src_path = self.parse_path(cmd[1])
                    if src_node is None:
                        continue
                        
                    dst_node, dst_path = self.parse_path(cmd[2])
                    if dst_node is None:
                        continue
                    
                    if src_node == dst_node:
                        result = self.server.route_command(src_node, action, src_path, dst_path)
                    else:
                        # Cross-node operation
                        if action == 'cp':
                            content = self.server.route_command(src_node, 'binary_read', src_path)
                            if isinstance(content, str) and content.startswith('Error:'):
                                print(content)
                                continue
                                
                            result = self.server.route_command(dst_node, 'binary_write', dst_path, content)
                        else:  # mv
                            try:
                                # 1. Read the source file content
                                content = self.server.route_command(src_node, 'binary_read', src_path)
                                if isinstance(content, str) and content.startswith('Error:'):
                                    print(content)
                                    continue
                                
                                # 2. Write to the target file
                                write_result = self.server.route_command(dst_node, 'binary_write', dst_path, content)
                                if isinstance(write_result, str) and write_result.startswith('Error:'):
                                    print(write_result)
                                    continue
                                
                                # 3. Delete the source file
                                delete_result = self.server.route_command(src_node, 'rm', src_path)
                                if isinstance(delete_result, str) and delete_result.startswith('Error:'):
                                    # If deletion fails, attempt to delete the target file that was written
                                    self.server.route_command(dst_node, 'rm', dst_path)
                                    print(delete_result)
                                    continue
                                
                                result = f"Moved '{cmd[1]}' to '{cmd[2]}'"
                            except Exception as e:
                                result = f"Error: Failed to move file - {str(e)}"
                    print(result)
                else:
                    print(f"Error: Invalid command '{action}'")
                    print("Enter 'help' for a list of available commands")

            except xmlrpc.client.Fault as e:
                print(f"Server error: {str(e)}")
            except xmlrpc.client.ProtocolError as e:
                print(f"Protocol error: {str(e)}")
            except ConnectionRefusedError:
                print("Error: Could not connect to the server, connection refused")
            except Exception as e:
                print(f"Error: {str(e)}")
                
        # Restore the original SIGINT handler
        signal.signal(signal.SIGINT, original_sigint_handler)

    def handle_interrupt(self, sig, frame):
        # When a Ctrl+C signal is caught, print a new line and display the command prompt
        print('\n', end='', flush=True)
        print(f"{self.hostname}> ", end='', flush=True)
        return

def cleanup_thread(p2p_system):
    """Thread to periodically clean up inactive nodes"""
    while True:
        try:
            inactive_nodes = p2p_system.cleanup_inactive_nodes(timeout=120)  # Increased timeout
            if inactive_nodes:
                print(f"Cleaned up {len(inactive_nodes)} inactive nodes")
            time.sleep(30)  # Check every 30 seconds
        except Exception as e:
            print(f"Cleanup thread error: {str(e)}")
            time.sleep(10)

def main():
    parser = argparse.ArgumentParser(description='P2P File System')
    parser.add_argument('--port', type=int, default=8000, help='Listening port')
    parser.add_argument('--connect', help='Connect to the specified server address')
    parser.add_argument('--hostname', help='Specify hostname (optional)')
    parser.add_argument('--key', help='Security key for connection verification (optional)')
    args = parser.parse_args()

    if args.connect:
        # First, start a local server
        fs = P2PFileSystem(args.port, args.key)
        server_thread = Thread(target=fs.start_server, daemon=True)
        server_thread.start()
        
        # Wait a moment for the server to start
        time.sleep(1)
        
        # Register local node (will be done by the client)
        
        # Then, connect to the central node as a client
        try:
            client = P2PClient(args.connect, args.port, args.hostname, args.key)
            client.run()
        except KeyboardInterrupt:
            print("\nExiting program...")
        except Exception as e:
            print(f"Client error: {str(e)}")
    else:
        # Start as the central node
        fs = P2PFileSystem(args.port, args.key)
        
        # Register local node
        hostname = args.hostname or socket.gethostname()
        if hostname.lower().startswith('id'):
            print(f"Error: Hostname cannot start with 'id'")
            sys.exit(1)
            
        fs.register_node('127.0.0.1', args.port, hostname, args.key)
        
        # Start node cleanup thread
        cleanup = Thread(target=cleanup_thread, args=(fs,), daemon=True)
        cleanup.start()
        
        try:
            fs.start_server()
        except KeyboardInterrupt:
            print("\nServer shutting down...")

if __name__ == '__main__':
    main()