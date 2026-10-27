# 简体中文本地化

本仓库是 [ComplianceAsCode/content](https://github.com/ComplianceAsCode/content)
的社区简体中文本地化 fork。它不是上游官方译本。

## 基线

- 上游仓库：`ComplianceAsCode/content`
- 基线分支：`master`
- 基线提交：`e4083bb6e9b61bb7aed4981ec12c8e53dda84c4d`
- 本地化分支：`zh-cn`

## 范围

翻译覆盖 `linux_os/`、`applications/` 和 `products/` 下的 2,566 个生产
`rule.yml`。每个规则只修改：

- `description`
- `rationale`

`title`、`fixtext`、OCIL、检查内容、修复脚本、模板变量、共享宏、profile、
control 以及其他代码和元数据保持英文原文。

## 呈现方式

英文内容保留在前，中文内容追加在后，并使用固定可见标记：

- Description：`<p><strong>中文说明：</strong></p>`
- Rationale：`<p><strong>中文理由：</strong></p>`

命令、路径、配置项、URL、Jinja 表达式、`<pre>` 代码块和标准标识符不翻译。
翻译规范与术语表见
[`translations/zh-CN/glossary.md`](translations/zh-CN/glossary.md)。

## 质量方法

中文内容采用 AI 辅助翻译和统一术语表生成，并通过完整性、英文基线哈希、
代码块一致性、非目标字段不变和构建验证。该方法用于技术可读性，不构成官方
认证或法律意义上的审校。

## 校验

```bash
python3 utils/zh_cn_translation.py validate --strict \
  --base-ref e4083bb6e9b61bb7aed4981ec12c8e53dda84c4d
```

生成样板审阅材料：

```bash
python3 utils/zh_cn_translation.py report \
  --rules-file translations/zh-CN/pilot-rules.txt \
  --output-dir build/zh-cn-pilot
```

英文原文哈希基线保存在 `translations/zh-CN/baseline.tsv`。如果上游英文内容
发生变化，校验会失败，必须重新审核中文后再更新基线。

## 上游同步

本 fork 以固定提交为基线，不自动跟随上游。上游新增或修改规则后，需要人工
决定是否同步，并重新翻译缺失或受影响的中文内容。

## 许可

上游的 BSD-3-Clause 许可证和版权声明继续适用，详见 [`LICENSE`](LICENSE)。
