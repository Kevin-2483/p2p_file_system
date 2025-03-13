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
        self.used_ids = set()  # 添加已使用ID集合
        self.file_manager = FileManager()
        self.nodes_lock = Lock()
        self.security_key = key

    def get_next_available_id(self):
        # 查找最小的可用ID
        used_ids = set(self.used_ids)
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        return next_id

    def register_node(self, ip_address, port, hostname, security_key=None):
        # 安全密钥验证
        if self.security_key and security_key != self.security_key:
            return {'error': '安全密钥验证失败'}
            
        # 先执行一次清理，以回收断连节点的ID
        self.cleanup_inactive_nodes()
            
        # 使用IP:端口作为节点标识
        node_key = f"{ip_address}:{port}"
        
        with self.nodes_lock:
            # 检查主机名是否已存在
            for node_info in self.nodes.values():
                if node_info['hostname'] == hostname:
                    return {'error': f'主机名 {hostname} 已被使用'}
                
            # 检查主机名是否以'id'开头
            if hostname.lower().startswith('id'):
                return {'error': f'主机名不能以"id"开头'}
            
            # 获取下一个可用ID
            next_id = self.get_next_available_id()
            self.used_ids.add(next_id)  # 将ID添加到已使用集合
            self.node_counter = max(self.node_counter, next_id)  # 更新计数器
            
            self.nodes[node_key] = {
                'id': next_id,
                'hostname': hostname,
                'ip': ip_address,
                'port': port,
                'last_active': time.time()
            }
            return {'id': next_id}

    def unregister_node(self, ip_address, port):
        node_key = f"{ip_address}:{port}"
        with self.nodes_lock:
            if node_key in self.nodes:
                node_id = self.nodes[node_key]['id']
                self.used_ids.remove(node_id)  # 从已使用集合中移除ID
                del self.nodes[node_key]
                return {'status': 'success', 'message': f'节点 {node_key} 已移除'}
            return {'status': 'error', 'message': f'节点 {node_key} 不存在'}

    def cleanup_inactive_nodes(self, timeout=60):
        current_time = time.time()
        inactive_nodes = []
        
        with self.nodes_lock:
            for node_key, node_info in list(self.nodes.items()):
                if (current_time - node_info.get('last_active', 0)) > timeout:
                    if node_info['ip'] != '127.0.0.1' or node_info['port'] != self.port:  # 不清理本地节点
                        inactive_nodes.append(node_key)
                        self.used_ids.remove(node_info['id'])  # 从已使用集合中移除ID
                        del self.nodes[node_key]
        
        return inactive_nodes

    def start_server(self):
        server = xmlrpc.server.SimpleXMLRPCServer(('0.0.0.0', self.port),
                                                 allow_none=True)
        server.register_instance(self)
        print(f"P2P节点启动于端口 {self.port}...")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n服务器关闭...")

    def route_command(self, node_id, command, *args):
        # 查找节点信息
        target_node = None
        
        with self.nodes_lock:
            for node_key, node_info in self.nodes.items():
                if node_info['id'] == node_id:
                    target_node = node_info.copy()
                    break
                    
        if not target_node:
            return f"错误：节点 {node_id} 不存在"
        
        # 检查是否是本地节点
        if target_node['ip'] == '127.0.0.1' and target_node['port'] == self.port:
            # 是本地节点，直接执行命令
            return getattr(self.file_manager, command)(*args)
        else:
            # 远程节点，转发请求
            try:
                # 使用节点正确的IP和端口创建代理
                proxy = xmlrpc.client.ServerProxy(f"http://{target_node['ip']}:{target_node['port']}")
                # 直接调用远程节点的文件管理命令
                return getattr(proxy, command)(*args)
            except Exception as e:
                return f"错误：连接到节点 {node_id} 失败 - {str(e)}"

    def get_nodes(self):
        with self.nodes_lock:
            return {ip: node_info for ip, node_info in self.nodes.items()}
    
    def get_node_by_hostname(self, hostname):
        with self.nodes_lock:
            for node_key, node_info in self.nodes.items():
                if node_info['hostname'] == hostname:
                    return node_info
            return None
            
    def get_help(self):
        help_text = """
P2P文件系统命令帮助:

基础命令:
  client                - 列出所有连接的节点
  exit                  - 退出客户端
  help                  - 显示此帮助信息

文件操作命令 (需指定节点ID或主机名):
  mkdir id节点:路径        - 创建目录
  rm id节点:路径           - 删除文件或目录
  touch id节点:路径        - 创建空文件
  ls id节点:路径           - 列出目录内容 (包含文件类型标记)
  tree id节点:路径         - 以树状结构显示目录
  cat id节点:路径          - 显示文件内容
  echo id节点:路径 内容     - 将内容写入文件
  cp 源id节点:路径 目标id节点:路径 - 复制文件
  mv 源id节点:路径 目标id节点:路径 - 移动文件

示例:
  mkdir id1:/test       - 在节点1创建/test目录
  ls id2:/              - 列出节点2的根目录内容
  cp id1:/file.txt id3:/backup.txt - 从节点1复制文件到节点3
  
也可以使用主机名代替ID:
  mkdir hostname1:/test - 在hostname1主机创建/test目录
  ls hostname2:/        - 列出hostname2主机的根目录内容

注意：所有路径操作都需要指定节点ID或主机名前缀
"""
        return help_text
        
    # 新增文件管理方法，直接转发到 FileManager
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
            return f"目录 '{path}' 创建成功"
        except Exception as e:
            return f"错误：创建目录失败 - {str(e)}"

    def rm(self, path):
        try:
            if os.path.isdir(path):
                os.rmdir(path)
                return f"目录 '{path}' 删除成功"
            elif os.path.isfile(path):
                os.remove(path)
                return f"文件 '{path}' 删除成功"
            else:
                return f"错误：'{path}' 不存在"
        except Exception as e:
            return f"错误：删除失败 - {str(e)}"

    def touch(self, path):
        try:
            with open(path, 'a'):
                os.utime(path, None)
            return f"文件 '{path}' 创建成功"
        except Exception as e:
            return f"错误：创建文件失败 - {str(e)}"

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
            return f"错误：列出目录失败 - {str(e)}"

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
            return f"错误：生成目录树失败 - {str(e)}"

    def cat(self, path):
        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"错误：读取文件失败 - {str(e)}"

    def echo(self, path, content):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            return f"内容已写入 '{path}'"
        except Exception as e:
            return f"错误：写入文件失败 - {str(e)}"

    def cp(self, src_path, dst_path):
        try:
            if os.path.isfile(src_path):
                # 确保目标目录存在
                dst_dir = os.path.dirname(os.path.abspath(dst_path))
                os.makedirs(dst_dir, exist_ok=True)
                
                with open(src_path, 'rb') as src:
                    with open(dst_path, 'wb') as dst:
                        dst.write(src.read())
                return f"已复制 '{src_path}' 到 '{dst_path}'"
            else:
                return f"错误：源文件 '{src_path}' 不存在或不是文件"
        except Exception as e:
            return f"错误：复制文件失败 - {str(e)}"

    def mv(self, src_path, dst_path):
        try:
            if not os.path.exists(src_path):
                return f"错误：源路径 '{src_path}' 不存在"
                
            # 确保目标目录存在
            dst_dir = os.path.dirname(os.path.abspath(dst_path))
            os.makedirs(dst_dir, exist_ok=True)
            
            os.rename(src_path, dst_path)
            return f"已移动 '{src_path}' 到 '{dst_path}'"
        except Exception as e:
            return f"错误：移动文件失败 - {str(e)}"

class P2PClient:
    def __init__(self, server_address, port, hostname=None, key=None):
        # 解析服务器地址和端口
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
        
        # 获取本机IP地址
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # 连接一个外部地址（不需要实际连接）来获取本地IP
            s.connect((server_address, connect_port))
            self.local_ip = s.getsockname()[0]
        finally:
            s.close()
            
        # 优先使用用户指定的主机名，如果未指定则使用系统主机名
        self.hostname = hostname or socket.gethostname()
        
        # 检查主机名是否以'id'开头
        if self.hostname.lower().startswith('id'):
            print(f"错误: 主机名不能以'id'开头")
            sys.exit(1)
            
        result = self.server.register_node(self.local_ip, self.port, self.hostname, self.security_key)
        if 'error' in result:
            print(f"错误: {result['error']}")
            sys.exit(1)
        self.node_id = result['id']
        
        # 初始化命令历史记录
        self.command_history = []
        self.setup_readline()
        
        # 创建心跳线程
        self.running = True
        self.heartbeat_thread = Thread(target=self.heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def setup_readline(self):
        # 设置 readline 以支持命令历史和编辑功能
        readline.parse_and_bind('"\\e[A": history-search-backward')  # 上箭头
        readline.parse_and_bind('"\\e[B": history-search-forward')   # 下箭头
        readline.parse_and_bind('"\\e[C": forward-char')             # 右箭头
        readline.parse_and_bind('"\\e[D": backward-char')            # 左箭头
        readline.parse_and_bind('"\\C-l": clear-screen')             # Ctrl+L 清屏
        
        # 如果历史文件存在，则加载
        histfile = os.path.expanduser('~/.p2p_history')
        try:
            readline.read_history_file(histfile)
            readline.set_history_length(1000)
        except FileNotFoundError:
            pass
            
        # 退出时保存历史
        import atexit
        atexit.register(readline.write_history_file, histfile)

    def heartbeat_loop(self):
        while self.running:
            try:
                self.server.heartbeat(self.local_ip, self.port)
                time.sleep(10)  # 每10秒发送一次心跳
            except Exception:
                # 心跳失败，但不打印错误信息以避免干扰用户界面
                time.sleep(5)  # 失败后稍等片刻再重试

    def parse_path(self, path_spec):
        """解析指定格式的路径，支持ID和主机名前缀"""
        if ':' not in path_spec:
            print(f"错误: 路径必须包含节点标识符，格式为 'idN:路径' 或 '主机名:路径'")
            return None, None
            
        prefix, path = path_spec.split(':', 1)
        
        # 检查是否是ID格式 (id后跟数字)
        if prefix.lower().startswith('id') and prefix[2:].isdigit():
            node_id = int(prefix[2:])
            return node_id, path
            
        # 否则视为主机名
        try:
            node_info = self.server.get_node_by_hostname(prefix)
            if not node_info:
                print(f"错误: 找不到主机名为 '{prefix}' 的节点")
                return None, None
            return node_info['id'], path
        except Exception as e:
            print(f"错误: 解析路径时发生错误 - {str(e)}")
            return None, None

    def run(self):
        # 屏蔽 Ctrl+C
        original_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self.handle_interrupt)
        
        # 主循环
        while self.running:
            try:
                # 更新命令提示符以显示主机名
                prompt = f"{self.hostname}> "
                cmd_input = input(prompt).strip()
                
                if not cmd_input:
                    continue
                    
                # 添加到命令历史
                readline.add_history(cmd_input)
                
                cmd = cmd_input.split()
                action = cmd[0]
                
                if action == 'exit':
                    self.running = False
                    # 注销节点
                    try:
                        self.server.unregister_node(self.local_ip, self.port)
                    except Exception:
                        pass  # 忽略注销错误
                    break
                    
                elif action == 'help':
                    print(self.server.get_help())
                    continue
                    
                elif action == 'client':
                    nodes = self.server.get_nodes()
                    print("\n已连接节点列表:")
                    print("-" * 60)
                    print(f"{'ID':<5} {'主机名':<15} {'地址':<20} {'端口':<6}")
                    print("-" * 60)
                    for ip, node_info in nodes.items():
                        print(f"id{node_info['id']:<3} {node_info['hostname']:<15} {node_info['ip']:<20} {node_info['port']:<6}")
                    print("-" * 60)
                    continue

                if action in ['mkdir', 'rm', 'touch', 'ls', 'tree', 'cat']:
                    if len(cmd) != 2:
                        print(f"用法: {action} 节点ID:路径")
                        print(f"示例: {action} id1:/home 或 {action} hostname:/home")
                        continue
                        
                    node_id, path = self.parse_path(cmd[1])
                    if node_id is None:
                        continue
                        
                    result = self.server.route_command(node_id, action, path)
                    print(result)
                elif action == 'echo':
                    if len(cmd) < 3:
                        print("用法: echo 节点ID:路径 内容")
                        print("示例: echo id1:/file.txt 文件内容 或 echo hostname:/file.txt 文件内容")
                        continue
                    
                    node_id, path = self.parse_path(cmd[1])
                    if node_id is None:
                        continue
                    
                    # 获取初始内容
                    initial_content = ' '.join(cmd[2:])
                    
                    # 初始化缓冲区和控制台状态
                    buffer = []
                    console = list(initial_content)
                    backtick_count = 0
                    in_multiline = False
                    i = 0
                    
                    while i < len(console):
                        if console[i] == '\\':
                            # 处理转义字符
                            if i + 1 < len(console):
                                buffer.append(console[i + 1])
                                i += 2
                                backtick_count = 0  # 重置反引号计数
                            else:
                                buffer.append('\\')
                                i += 1
                        elif console[i] == '`':
                            backtick_count += 1
                            if backtick_count == 3:
                                # 进入或退出多行模式
                                if not in_multiline:
                                    # 移除最后两个反引号
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
                            backtick_count = 0  # 重置反引号计数
                            i += 1
                    
                    # 如果在多行模式下，继续收集输入
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
                                    # 不包含结束的三重反引号
                                    buffer.extend(['\n'] + line_buffer[:-2])
                                    break
                                else:
                                    buffer.extend(['\n'] + line_buffer)
                                    
                            except EOFError:
                                print("输入终止。")
                                break
                    
                    final_content = ''.join(buffer)
                    
                    result = self.server.route_command(node_id, action, path, final_content)
                    print(result)
                elif action in ['cp', 'mv']:
                    if len(cmd) != 3:
                        print(f"用法: {action} 源节点ID:源路径 目标节点ID:目标路径")
                        print(f"示例: {action} id1:/src.txt id2:/dst.txt 或 {action} hostname1:/src.txt hostname2:/dst.txt")
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
                        # 跨节点操作
                        if action == 'cp':
                            content = self.server.route_command(src_node, 'cat', src_path)
                            if isinstance(content, str) and content.startswith('错误：'):
                                print(content)
                                continue
                                
                            result = self.server.route_command(dst_node, 'echo', dst_path, content)
                        else:  # mv
                            try:
                                # 1. 读取源文件内容
                                content = self.server.route_command(src_node, 'cat', src_path)
                                if isinstance(content, str) and content.startswith('错误：'):
                                    print(content)
                                    continue
                                
                                # 2. 写入目标文件
                                write_result = self.server.route_command(dst_node, 'echo', dst_path, content)
                                if isinstance(write_result, str) and write_result.startswith('错误：'):
                                    print(write_result)
                                    continue
                                
                                # 3. 删除源文件
                                delete_result = self.server.route_command(src_node, 'rm', src_path)
                                if isinstance(delete_result, str) and delete_result.startswith('错误：'):
                                    # 如果删除失败，尝试删除已写入的目标文件
                                    self.server.route_command(dst_node, 'rm', dst_path)
                                    print(delete_result)
                                    continue
                                
                                result = f"已移动 '{cmd[1]}' 到 '{cmd[2]}'"
                            except Exception as e:
                                result = f"错误：移动文件失败 - {str(e)}"
                    print(result)
                else:
                    print(f"错误: 无效命令 '{action}'")
                    print("输入 'help' 获取可用命令列表")

            except xmlrpc.client.Fault as e:
                print(f"服务器错误: {str(e)}")
            except xmlrpc.client.ProtocolError as e:
                print(f"协议错误: {str(e)}")
            except ConnectionRefusedError:
                print("错误: 无法连接到服务器，连接被拒绝")
            except Exception as e:
                print(f"错误: {str(e)}")
                
        # 恢复原始 SIGINT 处理
        signal.signal(signal.SIGINT, original_sigint_handler)

    def handle_interrupt(self, sig, frame):
        # 当捕获到 Ctrl+C 信号时，打印新行并显示命令提示符
        print('\n', end='', flush=True)
        print(f"{self.hostname}> ", end='', flush=True)
        return

def cleanup_thread(p2p_system):
    """定期清理不活跃节点的线程"""
    while True:
        try:
            inactive_nodes = p2p_system.cleanup_inactive_nodes(timeout=60)
            if inactive_nodes:
                print(f"已清理 {len(inactive_nodes)} 个不活跃节点")
            time.sleep(30)  # 每30秒检查一次
        except Exception as e:
            print(f"清理线程错误: {str(e)}")
            time.sleep(10)

def main():
    parser = argparse.ArgumentParser(description='P2P文件系统')
    parser.add_argument('--port', type=int, default=8000, help='监听端口')
    parser.add_argument('--connect', help='连接到指定的服务器地址')
    parser.add_argument('--hostname', help='指定主机名（可选）')
    parser.add_argument('--key', help='安全密钥，用于验证连接（可选）')
    args = parser.parse_args()

    if args.connect:
        # 首先启动一个本地服务器
        fs = P2PFileSystem(args.port, args.key)
        server_thread = Thread(target=fs.start_server, daemon=True)
        server_thread.start()
        
        # 然后作为客户端连接到中心节点
        try:
            client = P2PClient(args.connect, args.port, args.hostname, args.key)
            client.run()
        except KeyboardInterrupt:
            print("\n退出程序...")
        except Exception as e:
            print(f"客户端错误: {str(e)}")
    else:
        # 作为中心节点启动
        fs = P2PFileSystem(args.port, args.key)
        
        # 注册本地节点
        hostname = args.hostname or socket.gethostname()
        if hostname.lower().startswith('id'):
            print(f"错误: 主机名不能以'id'开头")
            sys.exit(1)
            
        fs.register_node('127.0.0.1', args.port, hostname)
        
        # 启动节点清理线程
        cleanup = Thread(target=cleanup_thread, args=(fs,), daemon=True)
        cleanup.start()
        
        try:
            fs.start_server()
        except KeyboardInterrupt:
            print("\n服务器关闭...")

if __name__ == '__main__':
    main()