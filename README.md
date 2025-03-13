# P2P 分布式文件系统

[English](./readme_en.md)

## 项目简介

P2P 分布式文件系统是一个基于 XML-RPC 的点对点文件系统，允许多个节点之间共享和管理文件。系统支持基本的文件操作，如创建、读取、更新和删除文件，以及在不同节点之间复制和移动文件。

特点：

- 节点自动发现和注册
- 基于 ID 和主机名的节点寻址
- 支持跨节点的文件操作
- 命令行界面，支持 Tab 自动补全（节点 ID/主机名）
- 路径语法高亮显示
- 命令历史记录（存储在 `.p2p_history` 文件中）
- 安全连接验证（可选）

## 架构设计

系统由以下主要组件构成：

1. **P2PFileSystem**：核心服务器组件，负责：

   - 节点注册和管理
   - 命令路由
   - 文件操作的转发

2. **FileManager**：文件操作管理器，实现：

   - 目录创建和删除
   - 文件创建、读取、写入和删除
   - 文件复制和移动

3. **P2PClient**：客户端组件，提供：

   - 命令行界面
   - 命令解析和执行
   - 节点间通信

## 安装说明

### 前提条件

- Python 3.6 或更高版本
- 标准库（无需额外依赖）

### 获取代码

```bash
git clone <repository-url>
cd <repository-directory>
```

## 使用说明

### 启动中心节点

```bash
python p2p_fs.py --port 8000 [--hostname <hostname>] [--key <security-key>]
```

### 连接到现有网络

```bash
python p2p_fs.py --port 8001 --connect <server-address>[:port] [--hostname <hostname>] [--key <security-key>]
```

### 命令行参数

- `--port`：指定监听端口（默认：8000）
- `--connect`：连接到指定的服务器地址
- `--hostname`：指定主机名（可选，默认使用系统主机名）
- `--key`：连接验证的安全密钥（可选）

## 命令帮助

### 基本命令

```
client                - 列出所有已连接节点
exit                  - 退出客户端
help                  - 显示帮助信息
```

### 文件操作命令（需要节点 ID 或主机名前缀）

```
mkdir idNode:path        - 创建目录
rm idNode:path           - 删除文件或目录
touch idNode:path        - 创建空文件
ls idNode:path           - 列出目录内容（带文件类型指示符）
tree idNode:path         - 以树形格式显示目录结构
cat idNode:path          - 显示文件内容
echo idNode:path content - 将内容写入文件
cp srcIdNode:path dstIdNode:path - 复制文件
mv srcIdNode:path dstIdNode:path - 移动文件
```

## 使用示例

### 启动节点

1. 启动中心节点：

```bash
python p2p_fs.py --port 8000 --hostname central-node
```

2. 启动并连接客户端节点：

```bash
python p2p_fs.py --port 8001 --connect localhost:8000 --hostname client-node1
```

### 基本操作示例

1. 查看已连接节点：

```
client-node1> client

Connected Nodes List:
------------------------------------------------------------
ID    Hostname         Address              Port
------------------------------------------------------------
id1   central-node     127.0.0.1            8000
id2   client-node1     192.168.1.101        8001
------------------------------------------------------------
```

2. 在节点上创建目录：

```
client-node1> mkdir id1:/shared
```

或使用主机名：

```
client-node1> mkdir central-node:/shared
```

3. 创建文件并写入内容：

```
client-node1> echo id1:/shared/hello.txt Hello, P2P File System!
```

4. 查看文件内容：

```
client-node1> cat id1:/shared/hello.txt
Hello, P2P File System!
```

5. 列出目录内容：

```
client-node1> ls id1:/shared
hello.txt
```

6. 在本地节点创建目录：

```
client-node1> mkdir id2:/local
```

7. 从远程节点复制文件到本地：

```
client-node1> cp id1:/shared/hello.txt id2:/local/hello_copy.txt
```

8. 查看目录树结构：

```
client-node1> tree id2:/
local/
├─ hello_copy.txt
```

### 多行内容输入

可以使用三个反引号 (```) 进入多行输入模式：

````
client-node1> echo id1:/shared/script.py ```
import os
import sys

print("Hello from P2P File System!")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
````

````

## 高级功能

### 安全连接

使用 `--key` 参数为节点设置安全密钥，只有具有相同密钥的节点才能连接：

```bash
# 中心节点
python p2p_fs.py --port 8000 --key secret123

# 客户端节点
python p2p_fs.py --port 8001 --connect localhost:8000 --key secret123
````

### 命令历史

命令历史记录保存在 `~/.p2p_history` 文件中，可以使用上下箭头键浏览历史命令。

## License

MIT Licensed. See LICENSE for details.
