# Fable Harness

> 一套即插即用的行为协议，让 Claude Code（Opus / Sonnet / Haiku）像个有纪律的工程师一样工作——动手前先查证、把假设讲清楚、重大结论先让人挑战过再采信、用真正的测试证明改动有效。

[English](README.md) &nbsp;·&nbsp; [繁體中文](README.zh-TW.md) &nbsp;·&nbsp; **简体中文** &nbsp;·&nbsp; [日本語](README.ja.md) &nbsp;·&nbsp; [한국어](README.ko.md)

![Version: 1.0.0](https://img.shields.io/badge/version-1.0.0-blue.svg) &nbsp; ![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## 这是什么

Fable Harness 是一个小型工具包——几个 hook、一个 skill、几个子代理——会在每次开启 Claude Code 会话时自动注入。它不会教 Claude 新招式，而是确保 Claude **每一次都照着一套有纪律的流程走**：先收集证据再回答、把假设讲出来而不是靠猜、对自己的重大结论先自我挑战，并且拿出真正的证据（而不是「看起来没问题」）证明改动真的有效。

可以把它想成是「行为的底线」，而不是完整的开发框架。它不会帮你排 sprint、不会帮你跑 CI 流水线——它做的是在智能体工作的过程中，让它保持诚实、谨慎、可验证。

## 为什么会有这个工具包

本项目提炼自第二次的 Fable 开放版本（Anthropic 的 Fable 模型）——那种谨慎、有纪律的做事方式。与其把这份纪律锁在单一模型里，这个工具包把它提炼成一套可复用的协议，用来强化 Opus（以及其他 Claude 模型）身边的工作架构，让不管是哪个模型在主导，都能维持同一套纪律。

坦白说在前面：hook 和 skill 只能移植「流程」本身（先取证、讲假设、交叉质疑结论、要求验证证据），没办法移植一个模型天生的判断力。但实际上，「表现得好」和「表现得随便」之间的差距，大多来自流程被跳过，而不是判断力不足。这正是这个工具包想补上的差距。

## 运作机制

- **OODA 循环**——回答前，Claude 先收集证据（实际搜索/读取文件，不靠训练记忆瞎猜），把假设讲出来，把任务转成一个可验证的目标（「让它能跑」这种说法不够），然后小步修改、每一步都验证。
- **多方对抗审查（adversarial review）**——这个工具包最具特色的机制。在采信一个重大结论之前（架构决策、根因判定、任何可能影响生产环境的结论），Claude 会**同时**派出三个独立的「反方」子代理，各自负责不同角度：**skeptic** 专找逻辑漏洞、**red-team** 专找安全与失效风险、**simplifier** 专找不必要的过度工程。三个视角里要过半「存活」（没被推翻），结论才算采信。
- **模型分工**——推理、架构设计、根因分析留给当下主导的模型；写代码与重构交给 Sonnet；批量文件处理、搜索、文本整理交给 Haiku。用刚好合适的模型做刚好合适的事。
- **完成定义（Definition of Done，TDD）**——只要改到实际逻辑，就要有自动化测试，并且证明「改之前测试会失败、改之后测试会通过」。单纯看输出顺不顺眼，或随手一个 `console.log`，都不算验证。
- **诚实汇报**——任何汇报的第一句话就是实际结果（不是铺垫），失败就照实讲，不美化。

## 里面有什么

| 组件 | 文件 | 作用 |
|---|---|---|
| 行为协议 | `.claude/hooks/fable_protocol.md` + `inject_protocol.sh` | 每次会话开始时注入 |
| 每轮微提醒 | `.claude/hooks/prompt_nudge.sh` | 用户每条消息都会被注入一行提醒 |
| 验证关卡 | `.claude/hooks/verify_gate.py` | 若这一轮改了代码却没跑测试，拦下收尾一次（第二次会放行） |
| 多方对抗审查 | `.claude/skills/adversarial-review/` | 定义上述三反方审查流程的 skill |
| 反方子代理 | `.claude/agents/{skeptic,red-team,simplifier}.md` | 对抗审查流程用的三个独立子代理角色 |
| 模型分工 | `CLAUDE.md` | 上面提到的分工表 |
| harness 检测器 | `scripts/detect_harness.py` | 只读检查——这个项目是不是已经有自己的开发 harness（例如 harnessmith、Superpowers），有的话 Fable 就退居底线角色 |
| 治理文档 | `diagnostics.md`、`model_dispatch_rules.md`、`cognitive_rubrics.md`、`future_session_letter.md` | 已知失效模式、子代理派工模板、何时该慢下来的判断准则、跨会话交接记录 |

## 快速开始

把这个仓库 clone 下来，然后跟你的 Claude Code 说：**「照 INSTALL.md 安装 Fable Harness。」** Claude 会自己读说明并安全地完成安装（先备份、绝不覆盖你已有的设置）。详细会做什么请看 [INSTALL.md](INSTALL.md)。

## 版本规则

本工具包采用[语义化版本（Semantic Versioning）](https://semver.org/lang/zh-CN/)——`主版本号.次版本号.修订号`，自 **1.0.0** 起：

- **主版本号（MAJOR）**——协议契约的破坏性改动（移除或改名 hook／skill／agent，或改变协议注入方式、子代理派工方式且不兼容），用户需重装或调整设置。
- **次版本号（MINOR）**——向后兼容的新增（新的 hook、skill、agent 或治理规则），已有安装可照常运行。
- **修订号（PATCH）**——向后兼容的修正或措辞调整（hook 修 bug、规则讲清楚、错别字）。

当前版本记在 [VERSION](VERSION)；重要变更记于 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

MIT — 详见 [LICENSE](LICENSE)（翻译版：[繁體中文](LICENSE.zh-TW)）。
