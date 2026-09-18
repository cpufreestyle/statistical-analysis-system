# 贡献指南

感谢你愿意参与。本项目的定位刻意保持「小」：**无构建步骤、无前端框架、运行时无云端依赖**。
能维持这点的改动最容易合并。

> English version: [CONTRIBUTING.md](CONTRIBUTING.md)

## 跑起来

```bash
python -m venv .venv

# Windows
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m src.cli web --port 5000

# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m src.cli web --port 5000
```

- 落地页：<http://127.0.0.1:5000/>
- 数据看板：<http://127.0.0.1:5000/app>
- 接口文档：<http://127.0.0.1:5000/docs>

冷启动会用 `data/*.csv` 自动播种 SQLite——**完全离线**，不需要任何 API Key。

## 六条会「静默坑人」的约定

完整理由见 `HANDOFF.md` §4。

1. **改完 `public/` 下任何文件，必须跑 `python scripts/embed_pages.py` 并重启服务。**
   Serverless 部署包读不到 `public/`，页面由内嵌的 `src/pages.py` 提供；不跑就会一直
   在排查「改了没生效」。
2. **标识符以中文规范键入库**，本地化只在 `data/labels.csv` + `src/labels.py` 一处发生。
   前端不翻译数据——`public/i18n.js` 只承载静态 UI 文案。
3. **未登记词条原样返回**，既不抛异常也不静默回退默认值。新增数据不得打断既有调用。
4. **密钥一律走环境变量**，禁止写进被跟踪的 `config.yaml`。
5. **一个变更批次 = 一个 tag + 一个 release**，不把无关批次合并发布。
6. **前端展示数据必须走公开端点。** 管理端点（`/api/db` `/api/reseed` `/api/kv-status`
   `/api/collect`）线上返回 403；`/api/stats` 正是为了让页面不依赖它们而存在。

## 新增或修改一个端点

四处要一起改，漏一处就会被 CI 或文档一致性测试拦下：

| 位置 | 改什么 |
| --- | --- |
| `src/web.py` | 路由本身 |
| `src/api_docs.py` | `ENDPOINTS`（pytest 会与 `app.url_map` **双向**比对） |
| `scripts/check_i18n.py` | `CHECKS`（双语契约） |
| `public/sitemap.xml` | 若是页面而非接口 |

## 测试与自检

```bash
.venv/Scripts/python.exe -m pytest -q            # 单元测试
.venv/Scripts/python.exe scripts/embed_pages.py  # 重新生成内嵌资源
python scripts/check_i18n.py                     # 双语契约（需服务在跑）
```

Markdown 在 CI 里用 `markdownlint-cli2` 检查（不阻塞），配置见 `.markdownlint.json`。

## 提交 Pull Request

- 提交信息用**中文** + 约定前缀：`feat:` / `fix:` / `docs:` / `test:` / `chore:`
  加一句简短中文摘要。
- 一个 PR 只做一个逻辑批次；行为或接口有变化时，同一批次内同步更新 `CHANGELOG.md`、
  `HANDOFF.md` 与两版 README。
- 填写 PR 模板里的检查清单（内嵌 / 测试 / i18n / 文档）。

## 反馈问题与安全

用 `.github/ISSUE_TEMPLATE/` 里的模板提 issue。涉及数据或凭据泄露的，请按 `SECURITY.md`
处理，不要在公开 issue 里描述细节。

## 许可证

提交贡献即表示你同意以 MIT 许可证发布你的改动（见 `LICENSE`）。
`data/` 下的公开数据集沿用其来源方各自的许可。
