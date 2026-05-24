# astrbot-code-inviter

AstrBot 多码池加好友发码插件项目。

本仓库用于承载 `astrbot_plugin_code_inviter` 的后续开发。目标是在 AstrBot 中通过 NapCat 接入机器人后，通过群触发、一次性好友验证 token、私聊领取和管理员导入导出能力，实现多码池邀请码 / 兑换码发放。

本项目只处理 AstrBot 插件这一条线，不涉及其他平台、其他接入层或额外中间服务。

## 当前状态

当前仓库已经实现插件骨架、配置解析、SQLite 存储、群触发 token、好友验证决策、私聊领取、管理员导入查询导出和禁领控制。

已确认的 v1 范围见 [docs/prd.md](docs/prd.md)。

## 已实现能力

- `metadata.yaml` 和 `main.py` 提供 AstrBot 插件入口。
- `_conf_schema.json` 提供后台配置 schema。
- 只有预设好的 `@命令词` 会进入插件状态机；裸文本和未知 `@xxx` 交由 AstrBot 原流程处理。
- 群聊 `@` 精确触发词生成一次性好友验证 token。
- 私聊 `@` 精确触发词按码池发放一个未使用码。
- SQLite 记录码、领取记录、待好友流程和禁领用户。
- 管理员可执行库存查询、文本导入、CSV 导入、领取记录查询、CSV 导出、禁领、解禁、码池管理和触发词管理。
- 领取规则已覆盖 `once_per_user`、`limited_per_user`、`limited_per_period` 和冷却时间。

## 触发规则

插件只接管白名单内的 `@命令词`。

```text
@领邀请码
@领取邀请码
@库存
@导入码 invite
@码池
@触发词 invite
```

不会接管：

```text
领邀请码
导入码：123test
@天气
@随便问问
```

码池触发词配置中不要写 `@`；实际发送时必须带 `@`。例如配置 `领邀请码` 后，用户输入 `@领邀请码` 才会进入插件流程。

## 管理命令

```text
@库存
@库存 invite
@统计
@统计 invite
@导入码 invite
CODE001
CODE002
@导入csv invite D:\path\codes.csv
@记录 123456789
@记录 123456789 invite
@导出领取记录 invite
@导出领取记录 invite 2026-05-01 2026-05-21
@重置领取 invite 123456789
@禁领 123456789
@解禁 123456789
@码池
@码池新增 beta 测试池
@码池修改 beta 新展示名
@码池禁用 beta
@码池启用 beta
@码池删除 beta
@触发词 invite
@触发词 invite 群 领邀请码,我要邀请码
@触发词 invite 私 领取邀请码
```

管理员命令只允许 `admin_users` 中的 QQ 号执行。
非管理员发送已预设的管理命令时，插件仍会接管并返回权限失败；未预设的 `@xxx` 不会接管。

## 时间单位

- `friend_gate.token_ttl_minutes`：一次性好友验证 token 有效期，单位：分钟。
- `claim_gate.group_source_ttl_hours`：群来源记录有效期，单位：小时。
- `claim_policy.cooldown_seconds`：同一用户两次领取之间的冷却时间，单位：秒。
- `claim_policy.period`：周期限制单位，可选 `none`、`day`、`week`、`month`。
- `claim_policy.period_limit`：每个周期领取上限，单位：次。

## AstrBot / NapCat 接入说明

群消息和私聊消息通过 AstrBot 的消息事件进入插件；NapCat 作为 AstrBot 的 OneBot 连接层，不需要额外中间服务。

好友申请审批通过 AstrBot 的 `OTHER_MESSAGE` 事件接入 OneBot request 原始事件；当 `request_type=friend` 且 token 校验通过时，插件会调用 aiocqhttp / NapCat 的 `set_friend_add_request` 动作同意申请。

## 本地验证

当前本地环境没有安装 AstrBot 运行时，因此单元测试覆盖业务逻辑、OneBot 好友申请适配 helper 和薄适配层；最终仍需要在 AstrBot + NapCat 实例中做一次端到端验证。

```powershell
python -B -m pytest -p no:cacheprovider tests
```

如果 Windows 临时目录出现 `WinError 5`，可指定工作区内的 `--basetemp`，或使用 Desktop Commander 运行同一条命令。

## 计划范围

- 多码池配置、触发词和领取规则。
- 群触发后生成一次性好友验证 token。
- 好友申请自动审批校验。
- 私聊领取单个未使用码。
- 文本列表和 CSV 批量导入。
- 库存、统计、查询和 CSV 导出管理命令。
- SQLite 本地持久化。

## 暂不包含

- 独立 Web 管理后台。
- 多机器人共享库存。
- 支付、订单、抽奖、积分等活动系统。
- 管理员补发功能。

## 开发计划

开发阶段和验证边界见 [docs/work-plan.md](docs/work-plan.md)。
