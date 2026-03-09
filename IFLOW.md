# MediaCrawler 项目概述

## 项目简介

MediaCrawler 是一个功能强大的多平台自媒体数据采集工具，支持小红书、抖音、快手、B站、微博、贴吧、知乎等主流平台的公开信息抓取。项目基于 Playwright 浏览器自动化框架实现登录并保存登录态，通过 JS 表达式获取签名参数，无需逆向复杂的加密算法。

## 技术栈

- **核心框架**: Playwright (浏览器自动化)
- **编程语言**: Python 3.9+
- **包管理**: uv (推荐) 或 pip
- **依赖管理**: requirements.txt
- **异步支持**: asyncio
- **命令行解析**: typer
- **数据库支持**: SQLite, MySQL (通过 aiomysql)
- **数据存储**: CSV, JSON, 数据库
- **代理支持**: 支持 IP 代理池
- **前端文档**: VitePress (package.json)

## 项目结构

```
MediaCrawler/
├── base/                  # 基础爬虫抽象类
├── browser_data/          # 浏览器用户数据目录
├── cache/                 # 缓存相关实现
├── cmd_arg/               # 命令行参数解析
├── config/                # 配置文件
├── constant/              # 常量定义
├── data/                  # 数据存储目录
├── database/              # 数据库相关
├── docs/                  # 文档
├── libs/                  # JavaScript库文件
├── media_platform/        # 各平台爬虫实现
│   ├── xhs/              # 小红书
│   ├── douyin/           # 抖音
│   ├── kuaishou/         # 快手
│   ├── bilibili/         # B站
│   ├── weibo/            # 微博
│   ├── tieba/            # 贴吧
│   └── zhihu/            # 知乎
├── model/                # 数据模型
├── proxy/                # 代理相关
├── store/                # 数据存储实现
├── test/                 # 测试文件
└── tools/                # 工具函数
```

## 核心配置

主要配置文件位于 `config/base_config.py`，关键配置项包括：

- `PLATFORM`: 目标平台 (xhs, dy, ks, bili, wb, tieba, zhihu)
- `KEYWORDS`: 搜索关键词
- `LOGIN_TYPE`: 登录方式 (qrcode, phone, cookie)
- `CRAWLER_TYPE`: 爬取类型 (search, detail, creator)
- `ENABLE_IP_PROXY`: 是否启用IP代理
- `HEADLESS`: 是否无头模式运行浏览器
- `SAVE_DATA_OPTION`: 数据保存方式 (csv, db, json, sqlite)
- `ENABLE_GET_COMMENTS`: 是否爬取评论
- `ENABLE_GET_MEIDAS`: 是否爬取媒体文件(图片/视频)

## 安装与运行

### 环境准备

1. 安装 uv: https://docs.astral.sh/uv/getting-started/installation
2. 安装 Node.js (>= 16.0.0): https://nodejs.org/en/download/

### 安装依赖

```bash
# 进入项目目录
cd MediaCrawler

# 使用 uv 安装依赖
uv sync

# 安装浏览器驱动
uv run playwright install
```

### 运行爬虫

```bash
# 关键词搜索爬取
uv run main.py --platform xhs --lt qrcode --type search

# 指定帖子ID爬取
uv run main.py --platform xhs --lt qrcode --type detail

# 查看帮助
uv run main.py --help
```

### 数据库初始化

```bash
# 初始化 SQLite 数据库
uv run main.py --init_db sqlite

# 初始化 MySQL 数据库
uv run main.py --init_db mysql
```

### 数据存储

支持多种数据存储方式:
- CSV 文件 (`data/` 目录下)
- JSON 文件 (`data/` 目录下)
- SQLite 数据库 (推荐个人用户)
- MySQL 数据库 (需要提前创建数据库)

## 开发约定

1. 遵循各平台的使用条款和robots.txt规则
2. 合理控制请求频率，避免给目标平台带来负担
3. 不得用于任何非法或不当的用途
4. 所有代码需遵守项目根目录下的LICENSE文件条款

## 注意事项

1. 项目仅供学习和研究目的使用
2. 严禁用于任何商业用途
3. 不得进行大规模爬取或对平台造成运营干扰
4. 使用前请详细阅读项目免责声明