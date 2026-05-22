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
- 群聊精确触发词生成一次性好友验证 token。
- 私聊精确触发词按码池发放一个未使用码。
- SQLite 记录码、领取记录、待好友流程和禁领用户。
- 管理员可执行库存查询、文本导入、CSV 导入、领取记录查询、CSV 导出、禁领和解禁。
- 领取规则已覆盖 `once_per_user`、`limited_per_user`、`limited_per_period` 和冷却时间。

## 管理命令

```text
/发码库存
/发码库存 invite
/导入码 invite
CODE001
CODE002
/导入csv invite D:\path\codes.csv
/查领取 123456789
/查领取 123456789 invite
/导出领取记录 invite
/导出领取记录 invite 2026-05-01 2026-05-21
/禁领 123456789
/解禁 123456789
```

管理员命令只允许 `admin_users` 中的 QQ 号执行。

## AstrBot / NapCat 接入说明

群消息和私聊消息通过 AstrBot 的消息事件进入插件；NapCat 作为 AstrBot 的 OneBot 连接层，不需要额外中间服务。

好友申请审批的业务判断已在 `src/friend_service.py` 和 `main.py::handle_friend_request` 中实现。不同 AstrBot / NapCat 版本暴露好友申请事件和同意申请动作的接口可能不同，部署时需要在真实 AstrBot + NapCat 环境中把对应事件参数传给 `handle_friend_request`，并在 `approved=True` 时调用 AstrBot / NapCat 的同意好友申请能力。

## 本地验证

当前本地环境没有安装 AstrBot 运行时，因此单元测试覆盖业务逻辑和薄适配层，真机验证需要在 AstrBot + NapCat 实例中完成。

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
