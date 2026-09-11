# 词途 · 高考 3500 词

一个基于 Flask、SQLite 和 ECDICT 的本地英语单词学习应用，支持新词学习、间隔复习、错词本、词库搜索以及多本自定义词书。

## 功能

- 新词学习：每次最多安排 30 个新词
- 间隔复习：根据掌握等级自动安排下次复习日期
- 错词本：记录当前不熟悉的单词
- 学习统计：查看累计学习、今日学习和掌握情况
- 词库：搜索、筛选、分页查看 ECDICT 词典数据
- 自定义词书：新建、编辑、导入、切换和删除词书
- 多词书进度：切换词书时不会丢失其他词书中的单词进度
- 浏览器发音：使用 Web Speech API 朗读英文单词

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python、Flask |
| 数据库 | SQLite |
| 词典数据 | ECDICT |
| 前端 | HTML、CSS、原生 JavaScript |
| 模板 | Jinja2 |

## 项目结构

```text
citu-3500words/
├── app.py                     # Flask 后端、数据库初始化和 API
├── requirements.txt           # Python 依赖
├── templates/
│   └── index.html             # 页面入口
├── static/
│   ├── script.js              # 学习、复习、词库和词书交互
│   └── style.css              # 页面样式
└── 03_data/
    ├── wordlist.txt           # 默认系统词书，一行一个单词
    ├── ecdict.csv             # ECDICT 词典数据
    ├── ECDICT_LICENSE         # ECDICT 原始许可证
    ├── README.md              # 数据文件说明
    └── vocabulary.db          # 自动生成的 SQLite 数据库
```

`vocabulary.db` 是运行时生成文件，已加入 `.gitignore`。

## 快速开始

### 1. 创建虚拟环境

Windows PowerShell：

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

macOS 或 Linux：

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动应用

```bash
python app.py
```

浏览器访问：

```text
http://127.0.0.1:5000
```

程序首次启动时可能花费几秒钟扫描 `ecdict.csv`，之后会复用 SQLite 数据和进程内缓存。

## 词表与词书

### 默认词书

默认词书来自：

```text
03_data/wordlist.txt
```

文件格式为一行一个单词：

```text
abandon
ability
able
abnormal
```

当前仓库中的默认词表包含 3395 个去重后的单词。原始数据不足 3500 个；需要完整 3500 词时，可以直接在 `wordlist.txt` 中继续补词。

修改 `wordlist.txt` 后重启应用，程序会重新生成当前词书对应的 `words` 数据。

### 自定义词书

在网页的“词库”页面可以：

- 新建自定义词书
- 直接粘贴单词列表
- 导入 `.txt` 文件
- 编辑已有自定义词书
- 切换当前词书
- 删除自定义词书

自定义词书保存在 `vocabulary.db` 中。当前选中的词书会同时用于学习、复习、错词本和词库。

## ECDICT 词典数据

ECDICT 项目地址：

<https://github.com/skywind3000/ECDICT>

本项目使用仓库中的：

```text
03_data/ecdict.csv
```

处理流程：

1. 读取当前词书的单词列表。
2. 从 `ecdict.csv` 查找对应词条。
3. 将音标、中文释义、英文释义、词形变化和考试标签写入 SQLite。
4. 未能在 ECDICT 中找到的单词仍会保留，但释义显示为“暂无释义”。
5. 英文大小写、标点差异以及部分常见别名会自动尝试匹配。

没有直接使用 ECDICT 提供的数百 MB SQLite 压缩包，而是使用原始 CSV 并只导入当前词书需要的单词。这样做可以让应用数据库更小，启动和查询速度更快。

## 数据库结构

SQLite 数据库文件：

```text
03_data/vocabulary.db
```

主要数据表：

| 表 | 作用 |
|---|---|
| `words` | 当前词书的单词及其 ECDICT 字段 |
| `word_books` | 默认词书和用户创建的自定义词书 |
| `word_progress` | 当前词书中的复习状态 |
| `progress_store` | 按单词保存的全局学习进度 |
| `study_log` | 每次“认识”或“不认识”的记录 |
| `app_meta` | 当前词书、导入签名和累计学习次数等元数据 |

### `words`

保存当前激活词书的单词和 ECDICT 数据，主要字段包括：

- `word`：单词
- `phonetic`：音标
- `meaning`：中文释义
- `definition`：英文释义
- `translation`：ECDICT 中文翻译
- `pos`：词性
- `exchange`：词形变化
- `tag`：考试标签
- `bnc`、`frq`：词频数据
- `collins`、`oxford`：词典星级或覆盖标记

### `word_books`

保存词书元数据和单词列表：

- 默认词书由 `wordlist.txt` 同步生成
- 自定义词书由网页创建或编辑
- 名字大小写不敏感且不可重复

### `progress_store`

按单词保存全局学习状态。即使某个单词不在当前词书中，它的掌握等级和错词状态也不会因为切换词书而丢失。再次切回包含该单词的词书时，进度会重新载入。

### `study_log`

记录每次学习事件，包括：

- 学习日期
- 单词
- 学习类型：`新词` 或 `复习`
- 结果：`known` 或 `unknown`

## 学习算法

### 认识

- `level + 1`，最高为 5
- 标记为已学习
- 从当前错词本移除
- 根据等级安排下次复习

| 等级 | 下次复习间隔 |
|---|---|
| 1 | 1 天 |
| 2 | 3 天 |
| 3 | 7 天 |
| 4 | 15 天 |
| 5 | 30 天 |

### 不认识

- `level - 1`，最低为 0
- 加入错词本
- 下次复习时间设为明天

## 主要接口

| 方法 | 路径 | 作用 |
|---|---|---|
| GET | `/api/today-words` | 获取今日新词 |
| GET | `/api/review-words` | 获取今日复习词 |
| GET | `/api/wrong-words` | 获取错词本 |
| GET | `/api/library` | 搜索、筛选和分页查看词库 |
| GET | `/api/wordbooks` | 获取词书列表 |
| POST | `/api/wordbooks` | 新建词书 |
| GET | `/api/wordbooks/<id>` | 获取词书详情和单词列表 |
| PUT | `/api/wordbooks/<id>` | 更新自定义词书 |
| DELETE | `/api/wordbooks/<id>` | 删除自定义词书 |
| POST | `/api/wordbooks/<id>/activate` | 切换当前词书 |
| POST | `/api/record` | 保存一次学习结果 |
| GET | `/api/stats` | 获取首页统计 |
| GET | `/api/statistics` | 获取详细统计 |
| POST | `/api/reset-progress` | 清空学习记录 |

## 开源协议建议

推荐本项目使用 **MIT License**。

理由：

- 协议简单，修改、分发、商用和闭源使用都比较方便。
- 与 ECDICT 当前使用的 MIT License 兼容。
- 适合这种工具型、学习型项目。
- 保留版权和许可证声明即可，约束较少。

仓库根目录已经提供 `LICENSE` 文件，版权人为 `xingmengchen888-gif`。

ECDICT 数据本身仍遵循其原许可证，包含在本仓库中的副本位于：

```text
03_data/ECDICT_LICENSE
```

发布或再分发时，应保留 ECDICT 的版权与许可证声明。若未来加入其他词典、考试词表或第三方数据，需要单独确认它们的授权条款。

## 注意事项

- `app.py` 使用 Flask 开发服务器，适合本地使用和开发调试，不适合直接用于生产环境。
- `vocabulary.db` 是本地学习数据，不应提交到公开仓库。
- 如果更换或删除了 `ecdict.csv`，需要重新生成词典数据。
- 代码和 ECDICT 数据都使用 MIT 许可证，但第三方数据是否允许再分发仍需按其原始协议确认。

## 致谢

- [ECDICT](https://github.com/skywind3000/ECDICT)：开放英汉词典数据
- [Flask](https://flask.palletsprojects.com/)：Web 框架
- [SQLite](https://www.sqlite.org/)：嵌入式数据库
