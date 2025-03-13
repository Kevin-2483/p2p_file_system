# P2P Distributed File System

## Project Overview

The P2P Distributed File System is a peer-to-peer file system built on XML-RPC, allowing multiple nodes to share and manage files.  The system supports basic file operations such as creating, reading, updating, and deleting files, as well as copying and moving files between different nodes.

Features:

-   Automatic node discovery and registration
-   Node addressing based on ID and hostname
-   Support for file operations across nodes
-   Command-line interface with tab auto-completion (for node IDs/hostnames)
-   Syntax highlighting for paths
-   Command history (stored in the `.p2p_history` file)
-   Optional secure connection verification

## Architecture Design

The system consists of the following main components:

1.  **P2PFileSystem**: The core server component, responsible for:

    -   Node registration and management
    -   Command routing
    -   Forwarding of file operations
2.  **FileManager**:  The file operation manager, implementing:

    -   Directory creation and deletion
    -   File creation, reading, writing, and deletion
    -   File copying and moving
3.  **P2PClient**: The client component, providing:

    -   Command-line interface
    -   Command parsing and execution
    -   Inter-node communication

## Installation Instructions

### Prerequisites

-   Python 3.6 or higher
-   Standard library (no additional dependencies required)

### Getting the Code

```bash
git clone <repository-url>
cd <repository-directory>
```

## Usage Instructions

### Starting the Central Node

```bash
python p2p_fs.py --port 8000 [--hostname <hostname>] [--key <security-key>]
```

### Connecting to an Existing Network

```bash
python p2p_fs.py --port 8001 --connect <server-address>[:port] [--hostname <hostname>] [--key <security-key>]
```

### Command-Line Arguments

-   `--port`: Specifies the listening port (default: 8000)
-   `--connect`: Connects to the specified server address.
-   `--hostname`: Specifies the hostname (optional, defaults to the system hostname).
-   `--key`:  The security key for connection verification (optional).

## Command Help

### Basic Commands

```
client                - List all connected nodes.
exit                  - Exit the client.
help                  - Display help information.
```

### File Operation Commands (Require Node ID or Hostname Prefix)

```
mkdir idNode:path        - Create a directory.
rm idNode:path           - Delete a file or directory.
touch idNode:path        - Create an empty file.
ls idNode:path           - List directory contents (with file type indicators).
tree idNode:path         - Display directory structure in a tree format.
cat idNode:path          - Display file contents.
echo idNode:path content - Write content to a file.
cp srcIdNode:path dstIdNode:path - Copy a file.
mv srcIdNode:path dstIdNode:path - Move a file.
```

## Usage Examples

### Starting Nodes

1.  Start the central node:

    ```bash
    python p2p_fs.py --port 8000 --hostname central-node
    ```

2.  Start and connect a client node:

    ```bash
    python p2p_fs.py --port 8001 --connect localhost:8000 --hostname client-node1
    ```

### Basic Operation Examples

1.  View connected nodes:

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

2.  Create a directory on a node:

    ```
    client-node1> mkdir id1:/shared
    ```

    Or using the hostname:

    ```
    client-node1> mkdir central-node:/shared
    ```

3.  Create a file and write content:

    ```
    client-node1> echo id1:/shared/hello.txt Hello, P2P File System!
    ```

4.  View file contents:

    ```
    client-node1> cat id1:/shared/hello.txt
    Hello, P2P File System!
    ```

5.  List directory contents:

    ```
    client-node1> ls id1:/shared
    hello.txt
    ```

6.  Create a directory on the local node:

```
client-node1> mkdir id2:/local
```

7. Copy file from remote node to local:
```
client-node1> cp id1:/shared/hello.txt id2:/local/hello_copy.txt
```

8. Display the directory's tree:
```
client-node1> tree id2:/
local/
├─ hello_copy.txt
```

### Multi-line Input

You can enter multi-line input mode using three backticks (```):

```
client-node1> echo id1:/shared/script.py ```
import os
import sys

print("Hello from P2P File System!")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
```

## Advanced Features

### Secure Connections

Use the `--key` argument to set a security key for the nodes.  Only nodes with the same key will be able to connect:

```bash
# Central node
python p2p_fs.py --port 8000 --key secret123

# Client node
python p2p_fs.py --port 8001 --connect localhost:8000 --key secret123
```

### Command History

Command history is saved in the `~/.p2p_history` file. You can use the up and down arrow keys to browse the command history.

## License

MIT Licensed. See LICENSE for details.
