# CANN-challenge

## 通过本地 VS Code 插件连接云端 SSH

以下步骤在运行 CANNLab/AtomGit 插件的**本地 Linux 主机**执行。插件把云端 SSH 转发到本机 `127.0.0.1` 的动态端口，并生成对应的临时密钥和 SSH 配置。连接期间应保持 VS Code 与插件转发服务运行。

### 1. 在插件中连接目标环境

在 VS Code 的 CANNLab/AtomGit 插件中选择云端环境并连接，等待 Remote-SSH 登录完成。随后在本地终端查看正在使用的 SSH 目标：

```bash
pgrep -a -x ssh
```

例如，进程参数中的 `devenvc_rr4pl.…atomgit.0` 是 SSH 配置别名。`ssh -D` 后面的端口是本地 SOCKS 代理端口，不是云端 SSH 的映射端口。

### 2. 确认当前别名、端口和临时密钥路径

插件生成的配置通常位于 `~/.atomgitdevenv/.ssh/config`，由 `~/.ssh/config` 通过 `Include` 引入。只查看连接字段，不需要读取私钥内容：

```bash
awk 'tolower($1) ~ /^(host|hostname|port|user|identityfile)$/ {print}' \
  ~/.atomgitdevenv/.ssh/config
```

配置中可能保留多个旧环境，应选择本次连接对应的 `Host`。下面的别名是 2026 年 9 月 30 日验证成功的示例，使用时替换为当前环境的完整别名：

```bash
ssh_target='devenvc_rr4pl.6ff9d294badc4a1bbe836f3fec2b3ec2.atomgit.0'

ssh -G "$ssh_target" |
  awk '$1 ~ /^(hostname|user|port|identityfile)$/ {print}'
```

确认生效的 `hostname` 为 `127.0.0.1`，并记录当前 `port`。`identityfile` 指向插件管理的临时密钥，通常位于 `~/.atomgitdevenv/.ssh/IdentityFile/`。使用 SSH 别名即可沿用该配置，无需复制私钥或手动拼接密钥路径；不要将临时私钥提交到仓库。

### 3. 验证端口与 SSH 登录

在同一个本地终端执行：

```bash
ssh_port=$(ssh -G "$ssh_target" 2>/dev/null | awk '$1 == "port" {print $2; exit}')
ss -ltnp "sport = :$ssh_port"

timeout 20s ssh \
  -o BatchMode=yes \
  -o ConnectTimeout=8 \
  -o ConnectionAttempts=1 \
  -o IdentitiesOnly=yes \
  "$ssh_target" \
  'printf "SSH_OK\n"; id -un; hostname; uname -m'
```

`ss` 有监听记录仅说明本地端口存在。SSH 命令返回 `SSH_OK`、远端用户、主机名和架构，且退出码为 `0`，才说明端口转发、密钥认证和远端命令执行均通过。

验证通过后，可以打开交互式终端：

```bash
ssh -o IdentitiesOnly=yes "$ssh_target"
```

### 验证记录与常见问题

2026 年 9 月 30 日实测：SSH 映射地址为 `127.0.0.1:45470`，通过插件临时密钥登录成功，远端用户为 `developer`，架构为 `aarch64`，验证命令退出码为 `0`。这只验证 SSH 连接，不代表已验证 NPU 运行或算子性能。

本次连接中几个端口的用途如下；它们都不应作为固定端口写入后续脚本：

| 本次端口 | 用途 |
| --- | --- |
| `45470` | 云端 SSH 的本地映射，来自当前别名的 `ssh -G` 输出 |
| `42935` | 插件转发管理服务，不能用于 SSH 登录 |
| `37193` | Remote-SSH 的本地 SOCKS 代理，对应进程参数 `-D` |

- `Connection refused`：检查当前 `Port` 是否监听，以及所选别名是否属于本次环境。旧配置和旧密钥文件存在，不代表旧端口仍可用。
- 连接超时：本地监听或转发链路可能未就绪，查看插件输出和 VS Code 的“Remote - SSH”日志。
- `Permission denied (publickey)`：已进入 SSH 认证阶段，核对当前别名、用户与 `IdentityFile`，避免使用其他环境的旧密钥。
- 环境重建、重连或插件重新启动后，重新执行上述定位与验证步骤；`127.0.0.1` 只指向运行插件的那台本地主机。
