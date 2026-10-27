# 简体中文翻译规范

本文件约束 `ComplianceAsCode/content` 中文 fork 中 `description` 与
`rationale` 的翻译。英文原文是唯一事实源，中文块不得改变安全要求、产品适用
范围或检查语义。

## 基本规则

- 使用简体中文和中国大陆网络安全技术文档语气。
- 规范强度依次使用“必须”“应”“禁止”“建议”“可”。
- 优先使用完整、可操作的技术表达，避免逐字硬译。
- 产品名、用户名、服务名、软件包名、命令、参数、路径、配置键、配置值、
  URL、标准编号和缩写保持英文。
- HTML 标签、Jinja 表达式和 `<pre>` 代码块保持原样。
- 中文块不得复制会输出英文散文的 `describe_*`、`ocil_*` 或
  `complete_*` 宏；应按相同参数写等价中文。只输出路径、值或标识符的宏可复用。
- 中文标点使用全角标点；英文标识符、路径和命令内部保留原有半角字符。
- 英文 `description` 与 `rationale` 内容不得修改。

## 固定标记

Description：

```html
<p><strong>中文说明：</strong></p>
```

Rationale：

```html
<p><strong>中文理由：</strong></p>
```

标记之后放置完整中文 XHTML 内容。若原文含 `<pre>`、列表或表格，中文块应保留
等价结构，并将其中代码原样复制。

## 术语表

| English | 中文 |
| --- | --- |
| access control | 访问控制 |
| account | 账户 |
| administrator | 管理员 |
| audit | 审计 |
| authentication | 身份验证 |
| authorization | 授权 |
| baseline | 基线 |
| benchmark | 基准 |
| boot loader | 引导加载程序 |
| boot partition | 引导分区 |
| certificate | 证书 |
| cluster | 集群 |
| compliance | 合规 |
| configuration | 配置 |
| control | 控制项 |
| credential | 凭据 |
| deny | 拒绝 |
| disable | 禁用 |
| enable | 启用 |
| encryption | 加密 |
| file group owner | 文件所属组 |
| file owner | 文件所有者 |
| file permissions | 文件权限 |
| firewall | 防火墙 |
| group | 组 |
| host | 主机 |
| identifier | 标识符 |
| integrity | 完整性 |
| kernel | 内核 |
| least privilege | 最小权限 |
| log | 日志 |
| mount option | 挂载选项 |
| mount point | 挂载点 |
| network | 网络 |
| owner | 所有者 |
| package | 软件包 |
| password | 密码 |
| permission | 权限 |
| policy | 策略 |
| privileged command | 特权命令 |
| profile | 配置档 |
| remote | 远程 |
| remediation | 修复 |
| required | 必须 |
| restrict | 限制 |
| rule | 规则 |
| scan | 扫描 |
| secure | 安全 |
| security context | 安全上下文 |
| service | 服务 |
| session | 会话 |
| should | 应 |
| system | 系统 |
| user | 用户 |
| verification | 验证 |
| vulnerability | 漏洞 |

以下保留英文：`root`、`sudo`、`SSH`、`SELinux`、`PAM`、`TLS`、`FIPS`、
`AIDE`、`auditd`、`systemd`、`grub2`、`nftables`、`iptables`、`CCE`、
`SRG`、`CIS`、`STIG`、`NIST`、`OSPP`、`OVAL`、`XCCDF`、`SCAP`。
