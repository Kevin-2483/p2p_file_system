# P2P Distributed File System

**Project Overview**

The P2P Distributed File System is a peer-to-peer file system based on XML-RPC, allowing multiple nodes to share and manage files. The system supports basic file operations such as create, read, update, and delete files, as well as copying and moving files between different nodes.

Features:

**	**•**	**Node automatic discovery and registration

**	**•**	**Node addressing based on ID and hostname

**	**•**	**Support for cross-node file operations

**	**•**	**Command-line interface with Tab autocomplete (for node ID/hostname)

**	**•**	**Path syntax highlighting

**	**•**	**Command history (stored in **.p2p_history** file)

**	**•**	**Optional secure connection verification

**Architecture Design**

The system consists of the following main components:

**	**1.**	****P2PFileSystem**: The core server component responsible for:

**	**•**	**Node registration and management

**	**•**	**Command routing

**	**•**	**Forwarding file operations

**	**2.**	****FileManager**: File operation manager that implements:

**	**•**	**Directory creation and deletion

**	**•**	**File creation, reading, writing, and deletion

**	**•**	**File copying and moving

**	**3.**	****P2PClient**: The client component that provides:

**	**•**	**Command-line interface

**	**•**	**Command parsing and execution

**	**•**	**Node-to-node communication

**Installation Instructions**

**Prerequisites**

**	**•**	**Python 3.6 or higher

**	**•**	**Standard library (no additional dependencies required)

**Get the Code**

```
git clone <repository-url>
cd <repository-directory>
```

**Usage Instructions**

**Start the Central Node**

```
python p2p_fs.py --port 8000 [--hostname <hostname>] [--key <security-key>]
```

**Connect to an Existing Network**

```
python p2p_fs.py --port 8001 --connect <server-address>[:port] [--hostname <hostname>] [--key <security-key>]
```

**Command-Line Parameters**

**	**•**	**--port: Specifies the listening port (default: 8000)

**	**•**	**--connect: Connect to the specified server address

**	**•**	**--hostname: Specify the hostname (optional, defaults to the system hostname)

**	**•**	**--key: Security key for connection verification (optional)

**Command Help**

**Basic Commands**

```
client                - List all connected nodes
exit                  - Exit the client
help                  - Display help information
```

**File Operation Commands (Requires Node ID or Hostname Prefix)**

```
mkdir idNode:path        - Create directory
rm idNode:path           - Delete file or directory
touch idNode:path        - Create empty file
ls idNode:path           - List directory contents (with file type indicators)
tree idNode:path         - Display directory structure in tree format
cat idNode:path          - Display file contents
echo idNode:path content - Write content to file
cp srcIdNode:path dstIdNode:path - Copy file
mv srcIdNode:path dstIdNode:path - Move file
```

**Example Usage**

**Start Node**

**	**1.**	**Start the central node:

```
python p2p_fs.py --port 8000 --hostname central-node
```

**	**2.**	**Start and connect the client node:

```
python p2p_fs.py --port 8001 --connect localhost:8000 --hostname client-node1
```

**Basic Operation Example**

**	**1.**	**View connected nodes:

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

**	**2.**	**Create a directory on a node:

```
client-node1> mkdir id1:/shared
```

Or use the hostname:

```
client-node1> mkdir central-node:/shared
```

**	**3.**	**Create a file and write content:

```
client-node1> echo id1:/shared/hello.txt Hello, P2P File System!
```

**	**4.**	**View file content:

```
client-node1> cat id1:/shared/hello.txt
Hello, P2P File System!
```

**	**5.**	**List directory contents:

```
client-node1> ls id1:/shared
hello.txt
```

**	**6.**	**Create a directory on the local node:

```
client-node1> mkdir id2:/local
```

**	**7.**	**Copy a file from a remote node to the local node:

```
client-node1> cp id1:/shared/hello.txt id2:/local/hello_copy.txt
```

**	**8.**	**View directory tree structure:

```
client-node1> tree id2:/
local/
├─ hello_copy.txt
```

**Multi-line Content Input**

You can enter multi-line input by using three backticks (```) to enter multi-line mode:

```
client-node1> echo id1:/shared/script.py ```
import os
import sys

print("Hello from P2P File System!")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
```

```
## Advanced Features

### Secure Connection

Use the `--key` parameter to set a security key for nodes, ensuring only nodes with the same key can connect:

```bash
# Central node
python p2p_fs.py --port 8000 --key secret123

# Client node
python p2p_fs.py --port 8001 --connect localhost:8000 --key secret123
```

**Command History**

Command history is saved in the **~/.p2p_history** file, and you can browse through previous commands using the up and down arrow keys.

**License**

MIT Licensed. See LICENSE for details.
