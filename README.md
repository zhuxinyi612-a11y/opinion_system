# 网络舆情数据采集模块 v2

## 目录结构

```text
opinion_crawler_template_v2/
├─ crawler/
│  ├─ main.py                  # 总入口
│  ├─ config.py                # 配置
│  ├─ http_client.py           # 请求、等待、重试
│  ├─ save_data.py             # 清洗、去重、保存
│  ├─ search_fallback.py       # 公开搜索索引兜底
│  ├─ news_crawler.py          # 新闻/GDELT
│  ├─ bilibili_crawler.py      # B站
│  ├─ weibo_crawler.py         # 微博 + 搜索索引兜底
│  ├─ zhihu_crawler.py         # 知乎 + 搜索索引兜底
│  ├─ toutiao_crawler.py       # 今日头条 + 搜索索引兜底
│  ├─ xiaohongshu_crawler.py   # 小红书搜索索引方向
│  └─ check_output.py          # 检查输出文件
├─ data/
├─ requirements.txt
├─ .env.example
└─ README.md
```

## 安装

```cmd
cd /d "D:\大型项目程序\opinion_crawler_template_v2"
pip install -r requirements.txt
```

## 稳定采集，推荐先跑这个

```cmd
python -m crawler.main --keywords "校园舆情" "暴雨灾害" "食品安全" "校园霸凌" "自然灾害" --pages 5 --platforms news bilibili
```

## 尽可能多平台采集

```cmd
python -m crawler.main --keywords "校园舆情" "暴雨灾害" "食品安全" "校园霸凌" "自然灾害" --pages 3 --platforms news bilibili weibo zhihu toutiao xiaohongshu
```

## 查看数据是否符合后端格式

```cmd
python -m crawler.check_output
```

输出文件：

```text
data/raw_data.json
```

字段格式：

```json
{
  "id": 10001,
  "title": "标题",
  "text": "正文或摘要",
  "time": "2026-07-01 10:30:00",
  "source": "来源",
  "url": "链接"
}
```

## 重要说明

微博、知乎、今日头条、小红书反爬和登录限制较强。v2 的策略是：

1. 先尝试公开站内接口或公开页面。
2. 如果结果很少，自动改用公开搜索索引兜底。
3. 不破解验证码，不破解签名，不绕过平台风控。
4. Cookie 只作为可选登录凭证，不建议使用主账号。

`.env` 不能上传 GitHub。
