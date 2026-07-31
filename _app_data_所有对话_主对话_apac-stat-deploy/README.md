# 亚太统计分析系统 (APAC Stats)

## 技术栈
- **前端**: 原生 HTML5 + CSS3 + JavaScript（零依赖）
- **后端**: Python Serverless Functions (Vercel)
- **部署**: Vercel

## 项目结构

```
apac-stat-deploy/
├── vercel.json          # Vercel 路由与构建配置
├── package.json         # 项目元信息
├── api/
│   └── index.py         # Python Serverless API 入口
└── public/
    ├── index.html       # 主页面
    ├── style.css        # 样式表
    └── app.js           # 交互逻辑
```

## 本地开发

```bash
# 安装 Vercel CLI（如未安装）
npm i -g vercel

# 本地开发预览
vercel dev

# 浏览器打开 http://localhost:3000
```

## 部署到 Vercel

### 方式一：命令行部署（推荐）

```bash
# 1. 进入项目目录
cd apac-stat-deploy

# 2. 登录 Vercel（首次需登录）
vercel login

# 3. 预览部署
vercel

# 4. 生产环境部署
vercel --prod
```

### 方式二：Git 部署

1. 将本目录推送到 GitHub/GitLab 仓库
2. 在 [Vercel Dashboard](https://vercel.com/dashboard) 点击 "New Project"
3. 导入仓库，Vercel 会自动检测配置
4. 点击 "Deploy" 即可

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/` | GET | 健康检查 |
| `/api/metrics` | GET | 获取核心指标数据 |
| `/api/sources` | GET | 获取数据源列表 |
| `/api/activities` | GET | 获取今日动态 |
| `/api/query` | POST | 提交查询请求 |

## 设计规范

- **配色**: 柔和蓝色体系（主色 #2B6BDB）
- **字体**: 思源黑体（Noto Sans SC）+ Roboto（数字）
- **排版**: 瑞士国际主义风格，严谨栅格，高信息密度
- **布局**: 左侧导航 + 主内容区（Tab 工作台） + 右侧边栏
