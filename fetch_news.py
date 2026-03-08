"""
量子日报 · LeQuantum
每天自动抓取量子科技新闻，调用Gemini API整理，生成静态网页
"""

import os
import json
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re

# ── 配置区 ──────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OUTPUT_FILE    = "index.html"
NEWS_COUNT     = 8
# ────────────────────────────────────────────────────────

RSS_SOURCES = [
    {"name": "Quantum Computing Report", "url": "https://quantumcomputingreport.com/feed/"},
    {"name": "ScienceDaily Quantum",     "url": "https://www.sciencedaily.com/rss/matter_energy/quantum_physics.xml"},
    {"name": "The Quantum Insider",      "url": "https://thequantuminsider.com/feed/"},
    {"name": "Phys.org Quantum",         "url": "https://phys.org/rss-feed/physics-news/quantum-physics/"},
]


def fetch_rss(source):
    articles = []
    try:
        req = urllib.request.Request(source["url"], headers={"User-Agent": "LeQuantum/1.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
        for item in items[:5]:
            def get(tag):
                n = item.find(tag)
                return n.text.strip() if n is not None and n.text else ""
            title   = get("title")
            link    = get("link") or get("url")
            summary = get("description") or get("{http://www.w3.org/2005/Atom}summary") or ""
            pubdate = get("pubDate") or get("{http://www.w3.org/2005/Atom}updated") or ""
            summary = re.sub(r"<[^>]+>", "", summary)[:500]
            if title and link:
                articles.append({
                    "source":  source["name"],
                    "title":   title,
                    "link":    link,
                    "summary": summary,
                    "date":    pubdate[:16] if pubdate else "未知日期",
                })
    except Exception as e:
        print(f"  ⚠ 抓取失败 {source['name']}: {e}")
    return articles


def call_gemini(prompt):
    if not GEMINI_API_KEY:
        return "[]"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4000}
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def process_with_ai(raw_articles):
    articles_text = "\n\n".join([
        f"来源: {a['source']}\n标题: {a['title']}\n摘要: {a['summary']}\n链接: {a['link']}\n日期: {a['date']}"
        for a in raw_articles
    ])
    prompt = f"""你是量子科技新闻编辑。从下面的原始新闻中，选出最重要的{NEWS_COUNT}条，整理成JSON格式。

要求：
1. 优先选择最新的、影响最大的新闻
2. 把英文标题和摘要翻译成中文，语言要通俗易懂，让普通人也能看懂
3. 给每条新闻打上标签（从以下选：量子计算、量子通信、量子传感、材料科学、融资、政策、硬件、算法）
4. 判断重要性（high/medium/low）
5. 只返回JSON数组，不要任何其他文字，不要markdown代码块

输出格式：
[
  {{
    "title_zh": "中文标题",
    "title_en": "English title",
    "summary_zh": "中文摘要（100字以内，通俗易懂）",
    "source": "来源名称",
    "link": "原文链接",
    "date": "日期",
    "tags": ["标签1", "标签2"],
    "importance": "high"
  }}
]

原始新闻：
{articles_text}
"""
    try:
        result = call_gemini(prompt)
        result = result.strip()
        result = re.sub(r'^```json\s*', '', result)
        result = re.sub(r'^```\s*', '', result)
        result = re.sub(r'\s*```$', '', result)
        match = re.search(r'\[.*\]', result, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"  ⚠ AI处理失败: {e}")
    return [{
        "title_zh": a["title"], "title_en": a["title"],
        "summary_zh": a["summary"][:200], "source": a["source"],
        "link": a["link"], "date": a["date"],
        "tags": ["量子科技"], "importance": "medium"
    } for a in raw_articles[:NEWS_COUNT]]


def get_tag_style(tag):
    return {"量子计算":"tag-blue","量子通信":"tag-purple","量子传感":"tag-gold",
            "材料科学":"tag-gold","融资":"tag-purple","政策":"tag-gold",
            "硬件":"tag-blue","算法":"tag-blue"}.get(tag,"tag-blue")

def get_card_style(importance, index):
    if importance=="high": return ["card-blue","card-purple","card-gold","card-red"][index%4]
    return ["card-blue","card-purple"][index%2]


def generate_html(articles, today):
    hero = articles[0] if articles else {}
    grid_articles = articles[1:5]
    analysis_articles = articles[5:8]

    ticker_items = "".join([
        f'<span class="ticker-item">{a.get("title_zh","")} · {a.get("source","")}</span>'
        for a in articles[:6]
    ] * 2)

    hero_tags = "".join([
        f'<span class="tag {get_tag_style(t)}">{t}</span>'
        for t in hero.get("tags",[])[:3]
    ])

    grid_html = ""
    for i, a in enumerate(grid_articles):
        tags_html = "".join([f'<span class="tag {get_tag_style(t)}">{t}</span>' for t in a.get("tags",[])[:2]])
        grid_html += f"""
        <a href="{a.get('link','#')}" target="_blank" style="text-decoration:none;">
          <div class="news-card {get_card_style(a.get('importance','medium'),i)}">
            <div class="source-badge">{a.get('source','')} · {a.get('date','')[:10]}</div>
            <div class="article-tags">{tags_html}</div>
            <h3 class="article-title">{a.get('title_zh','')}</h3>
            <p class="article-excerpt">{a.get('summary_zh','')}</p>
            <div class="article-footer">
              <span class="meta-item">📅 {a.get('date','')[:10]}</span>
              <span class="read-more">阅读原文 →</span>
            </div>
          </div>
        </a>"""

    analysis_html = ""
    for i, a in enumerate(analysis_articles):
        colors = ["var(--accent)","var(--accent2)","var(--gold)"]
        nums   = ["01","02","03"]
        analysis_html += f"""
        <a href="{a.get('link','#')}" target="_blank" style="text-decoration:none;">
          <div class="analysis-card">
            <div class="analysis-num" style="color:{colors[i]}">{nums[i]}</div>
            <h3 class="analysis-title">{a.get('title_zh','')}</h3>
            <p class="analysis-body">{a.get('summary_zh','')}</p>
            <div style="margin-top:12px;font-family:var(--mono);font-size:10px;color:var(--muted)">
              {a.get('source','')} · {a.get('date','')[:10]}
            </div>
          </div>
        </a>"""

    company_html = ""
    seen = set()
    for a in articles[:5]:
        src = a.get("source","")
        if src not in seen:
            seen.add(src)
            company_html += f"""
            <div class="company-item">
              <div class="company-logo" style="background:rgba(0,212,255,0.1);color:var(--accent)">{src[0].upper()}</div>
              <div class="company-info">
                <div class="company-name">{src}</div>
                <div class="company-update">{a.get('title_zh','')[:28]}...</div>
              </div>
              <div class="activity-dot dot-active"></div>
            </div>"""

    sources_str = " · ".join(list(set(a.get("source","") for a in articles[:4])))

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LeQuantum · 量子每天一口 · {today}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;900&family=Space+Mono:wght@400;700&family=Outfit:wght@300;400;700;900&display=swap" rel="stylesheet">
<style>
  :root{{--black:#0a0a0f;--deep:#0d0d1a;--card:#111120;--border:rgba(100,180,255,0.12);--accent:#00d4ff;--accent2:#7b4fff;--gold:#f0c040;--text:#e8eaf2;--muted:#6b7089;--serif:'Noto Serif SC',serif;--mono:'Space Mono',monospace;--sans:'Outfit',sans-serif;}}
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:var(--black);color:var(--text);font-family:var(--sans);min-height:100vh;overflow-x:hidden;}}
  body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px);background-size:60px 60px;pointer-events:none;z-index:0;}}
  a{{color:inherit;}}
  header{{position:relative;z-index:10;border-bottom:1px solid var(--border);padding:0 40px;}}
  .header-top{{display:flex;align-items:center;justify-content:space-between;padding:20px 0 16px;border-bottom:1px solid var(--border);}}
  .logo{{display:flex;align-items:center;gap:12px;}}
  .logo-mark{{font-family:'Outfit',sans-serif;font-weight:900;font-size:26px;letter-spacing:-0.02em;}}
  .logo-mark .le{{color:rgba(255,255,255,0.4);}}
  .logo-mark .q{{background:linear-gradient(135deg,#00d4ff,#7b4fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
  .logo-dot{{width:6px;height:6px;background:var(--accent);border-radius:50%;animation:pulse 2s ease-in-out infinite;}}
  @keyframes pulse{{0%,100%{{opacity:1;box-shadow:0 0 0 0 rgba(0,212,255,0.4);}}50%{{opacity:0.7;box-shadow:0 0 0 6px rgba(0,212,255,0);}}}}
  .logo-sub{{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:0.15em;}}
  .header-right{{display:flex;align-items:center;gap:16px;}}
  .date-badge{{font-family:var(--mono);font-size:11px;color:var(--muted);}}
  .live-badge{{font-family:var(--mono);font-size:9px;color:#4ade80;background:rgba(74,222,128,0.08);border:1px solid rgba(74,222,128,0.2);padding:4px 10px;border-radius:4px;display:flex;align-items:center;gap:5px;}}
  .live-dot{{width:5px;height:5px;background:#4ade80;border-radius:50%;animation:pulse 1.5s ease-in-out infinite;}}
  .nav-bar{{display:flex;gap:28px;padding:13px 0;align-items:center;}}
  .nav-item{{font-size:11px;letter-spacing:0.08em;color:var(--muted);cursor:pointer;text-transform:uppercase;font-weight:500;transition:color 0.2s;}}
  .nav-item:hover,.nav-item.active{{color:var(--text);}}
  .nav-item.active{{color:var(--accent);border-bottom:1px solid var(--accent);padding-bottom:2px;}}
  .nav-right{{margin-left:auto;}}
  .sub-btn{{background:linear-gradient(135deg,var(--accent2),var(--accent));color:var(--black);border:none;padding:8px 18px;border-radius:6px;font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:0.08em;cursor:pointer;}}
  .ticker-bar{{background:rgba(0,212,255,0.05);border-bottom:1px solid var(--border);padding:9px 40px;display:flex;align-items:center;gap:14px;overflow:hidden;position:relative;z-index:10;}}
  .ticker-label{{font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.2em;color:var(--accent);white-space:nowrap;background:rgba(0,212,255,0.08);padding:3px 8px;border-radius:3px;border:1px solid rgba(0,212,255,0.15);}}
  .ticker-track{{display:flex;gap:50px;animation:ticker 40s linear infinite;white-space:nowrap;}}
  .ticker-track:hover{{animation-play-state:paused;}}
  @keyframes ticker{{0%{{transform:translateX(0);}}100%{{transform:translateX(-50%);}}}}
  .ticker-item{{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:8px;}}
  .ticker-item::before{{content:'◆';color:var(--accent2);font-size:7px;}}
  main{{position:relative;z-index:5;max-width:1380px;margin:0 auto;padding:36px 40px;display:grid;grid-template-columns:1fr 330px;gap:36px;}}
  .source-badge{{display:inline-flex;align-items:center;gap:4px;font-family:var(--mono);font-size:9px;letter-spacing:0.1em;color:#4ade80;background:rgba(74,222,128,0.05);border:1px solid rgba(74,222,128,0.12);padding:2px 8px;border-radius:3px;margin-bottom:10px;}}
  .source-badge::before{{content:'✓';}}
  .section-label{{font-family:var(--mono);font-size:9px;letter-spacing:0.25em;color:var(--accent);text-transform:uppercase;margin-bottom:18px;display:flex;align-items:center;gap:10px;}}
  .section-label::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent);}}
  .hero-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:20px;cursor:pointer;transition:border-color 0.3s,transform 0.3s;position:relative;display:block;text-decoration:none;}}
  .hero-card:hover{{border-color:rgba(0,212,255,0.3);transform:translateY(-2px);}}
  .hero-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--accent2),var(--accent));}}
  .hero-visual{{height:160px;background:radial-gradient(ellipse at 30% 50%,rgba(123,79,255,0.2) 0%,transparent 60%),radial-gradient(ellipse at 80% 30%,rgba(0,212,255,0.15) 0%,transparent 50%),var(--deep);display:flex;align-items:center;justify-content:center;overflow:hidden;}}
  .orbit-wrap{{width:130px;height:130px;position:relative;}}
  .orbit{{position:absolute;border:1px solid rgba(0,212,255,0.2);border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%);}}
  .o1{{width:50px;height:50px;animation:spin 4s linear infinite;}}
  .o2{{width:86px;height:86px;animation:spin 7s linear infinite reverse;border-color:rgba(123,79,255,0.25);}}
  .o3{{width:120px;height:120px;animation:spin 11s linear infinite;border-color:rgba(0,212,255,0.1);}}
  @keyframes spin{{from{{transform:translate(-50%,-50%) rotate(0deg);}}to{{transform:translate(-50%,-50%) rotate(360deg);}}}}
  .nucleus{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:14px;height:14px;background:radial-gradient(circle,var(--accent),var(--accent2));border-radius:50%;box-shadow:0 0 18px rgba(0,212,255,0.7);}}
  .electron{{position:absolute;width:5px;height:5px;background:var(--accent);border-radius:50%;box-shadow:0 0 7px var(--accent);top:-2.5px;left:calc(50% - 2.5px);}}
  .hero-body{{padding:22px 26px 26px;}}
  .article-tags{{display:flex;gap:7px;margin-bottom:12px;flex-wrap:wrap;}}
  .tag{{font-family:var(--mono);font-size:9px;letter-spacing:0.1em;padding:3px 8px;border-radius:3px;text-transform:uppercase;font-weight:700;}}
  .tag-blue{{background:rgba(0,212,255,0.1);color:var(--accent);border:1px solid rgba(0,212,255,0.2);}}
  .tag-purple{{background:rgba(123,79,255,0.1);color:#a78bff;border:1px solid rgba(123,79,255,0.2);}}
  .tag-gold{{background:rgba(240,192,64,0.1);color:var(--gold);border:1px solid rgba(240,192,64,0.2);}}
  .tag-red{{background:rgba(255,80,80,0.1);color:#ff6060;border:1px solid rgba(255,80,80,0.2);}}
  .article-title{{font-family:var(--serif);font-size:20px;font-weight:600;line-height:1.5;margin-bottom:9px;color:#fff;}}
  .article-title-en{{font-family:var(--mono);font-size:11px;color:var(--muted);margin-bottom:12px;line-height:1.5;}}
  .article-excerpt{{font-size:13px;line-height:1.85;color:rgba(232,234,242,0.68);margin-bottom:18px;}}
  .article-footer{{display:flex;align-items:center;justify-content:space-between;}}
  .meta-item{{font-family:var(--mono);font-size:10px;color:var(--muted);}}
  .read-more{{font-family:var(--mono);font-size:11px;color:var(--accent);cursor:pointer;display:flex;align-items:center;gap:5px;transition:gap 0.2s;}}
  .read-more:hover{{gap:9px;}}
  .news-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px;}}
  .news-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;cursor:pointer;transition:border-color 0.3s,transform 0.2s;position:relative;overflow:hidden;}}
  .news-card:hover{{border-color:rgba(0,212,255,0.25);transform:translateY(-1px);}}
  .news-card::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;opacity:0;transition:opacity 0.3s;}}
  .news-card:hover::after{{opacity:1;}}
  .card-blue::after{{background:linear-gradient(90deg,var(--accent),transparent);}}
  .card-purple::after{{background:linear-gradient(90deg,var(--accent2),transparent);}}
  .card-gold::after{{background:linear-gradient(90deg,var(--gold),transparent);}}
  .card-red::after{{background:linear-gradient(90deg,#ff6060,transparent);}}
  .news-card .article-title{{font-size:14px;margin-bottom:7px;}}
  .news-card .article-excerpt{{font-size:11px;margin-bottom:11px;-webkit-line-clamp:3;display:-webkit-box;-webkit-box-orient:vertical;overflow:hidden;}}
  .analysis-strip{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;}}
  .analysis-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px;cursor:pointer;transition:border-color 0.3s;}}
  .analysis-card:hover{{border-color:rgba(0,212,255,0.25);}}
  .analysis-num{{font-family:var(--mono);font-size:32px;font-weight:700;line-height:1;margin-bottom:8px;opacity:0.12;}}
  .analysis-title{{font-family:var(--serif);font-size:14px;font-weight:600;color:#fff;margin-bottom:7px;line-height:1.4;}}
  .analysis-body{{font-size:11px;color:rgba(232,234,242,0.5);line-height:1.7;}}
  .sidebar{{grid-column:2;display:flex;flex-direction:column;gap:18px;}}
  .sidebar-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;}}
  .sidebar-title{{font-family:var(--mono);font-size:9px;letter-spacing:0.2em;color:var(--accent);text-transform:uppercase;margin-bottom:14px;padding-bottom:11px;border-bottom:1px solid var(--border);}}
  .company-list{{display:flex;flex-direction:column;gap:9px;}}
  .company-item{{display:flex;align-items:center;gap:10px;padding:9px;background:rgba(255,255,255,0.02);border-radius:6px;}}
  .company-logo{{width:30px;height:30px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:10px;font-weight:700;flex-shrink:0;}}
  .company-info{{flex:1;min-width:0;}}
  .company-name{{font-size:11px;font-weight:500;color:var(--text);}}
  .company-update{{font-size:10px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
  .activity-dot{{width:5px;height:5px;border-radius:50%;flex-shrink:0;}}
  .dot-active{{background:#4ade80;box-shadow:0 0 5px #4ade80;}}
  .subscribe-widget{{background:linear-gradient(135deg,rgba(123,79,255,0.08),rgba(0,212,255,0.04));border:1px solid rgba(123,79,255,0.18);}}
  .subscribe-desc{{font-size:12px;color:rgba(232,234,242,0.55);line-height:1.7;margin-bottom:12px;}}
  .email-input{{width:100%;background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:6px;padding:9px 12px;color:var(--text);font-family:var(--sans);font-size:12px;margin-bottom:7px;outline:none;}}
  .email-input::placeholder{{color:var(--muted);}}
  .sub-full-btn{{width:100%;background:linear-gradient(135deg,var(--accent2),var(--accent));color:var(--black);border:none;padding:9px;border-radius:6px;font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:0.08em;cursor:pointer;}}
  footer{{position:relative;z-index:5;border-top:1px solid var(--border);padding:20px 40px;display:flex;align-items:center;justify-content:space-between;margin-top:16px;}}
  .footer-logo{{font-family:'Outfit',sans-serif;font-weight:900;font-size:15px;background:linear-gradient(135deg,#00d4ff,#7b4fff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;opacity:0.7;}}
  .footer-copy{{font-family:var(--mono);font-size:10px;color:var(--muted);margin-left:14px;}}
  .footer-links{{display:flex;gap:18px;}}
  .footer-link{{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:0.1em;text-transform:uppercase;cursor:pointer;}}
  @keyframes fadeInUp{{from{{opacity:0;transform:translateY(16px);}}to{{opacity:1;transform:translateY(0);}}}}
  .hero-card{{animation:fadeInUp 0.5s ease both;}}
  .news-card:nth-child(1){{animation:fadeInUp 0.5s 0.08s ease both;}}
  .news-card:nth-child(2){{animation:fadeInUp 0.5s 0.12s ease both;}}
  .news-card:nth-child(3){{animation:fadeInUp 0.5s 0.16s ease both;}}
  .news-card:nth-child(4){{animation:fadeInUp 0.5s 0.20s ease both;}}
  @media(max-width:900px){{main{{grid-template-columns:1fr;padding:20px;}}
  .sidebar{{grid-column:1;}}.analysis-strip{{grid-template-columns:1fr;}}.news-grid{{grid-template-columns:1fr;}}
  header{{padding:0 20px;}}footer{{padding:16px 20px;flex-direction:column;gap:10px;}}}}
</style>
</head>
<body>
<header>
  <div class="header-top">
    <div class="logo">
      <div class="logo-dot"></div>
      <div class="logo-mark"><span class="le">le</span><span class="q">quantum</span></div>
      <span class="logo-sub">量子 · 每天一口</span>
    </div>
    <div class="header-right">
      <span class="date-badge">{today}</span>
      <div class="live-badge"><div class="live-dot"></div>真实来源</div>
    </div>
  </div>
  <nav class="nav-bar">
    <span class="nav-item active">今日动态</span>
    <span class="nav-item">深度分析</span>
    <span class="nav-item">公司追踪</span>
    <span class="nav-item">量子比特</span>
    <div class="nav-right"><button class="sub-btn">订阅简报 ↗</button></div>
  </nav>
</header>

<div class="ticker-bar">
  <span class="ticker-label">● LIVE</span>
  <div class="ticker-track">{ticker_items}</div>
</div>

<main>
  <div>
    <div class="section-label">今日头条 · TOP STORY</div>
    <a href="{hero.get('link','#')}" target="_blank" class="hero-card">
      <div class="hero-visual">
        <div class="orbit-wrap">
          <div class="orbit o1"><div class="electron"></div></div>
          <div class="orbit o2"></div>
          <div class="orbit o3"></div>
          <div class="nucleus"></div>
        </div>
      </div>
      <div class="hero-body">
        <div class="source-badge">{hero.get('source','')} · {hero.get('date','')[:10]}</div>
        <div class="article-tags"><span class="tag tag-gold">● 头条</span>{hero_tags}</div>
        <h1 class="article-title">{hero.get('title_zh','')}</h1>
        <p class="article-title-en">{hero.get('title_en','')}</p>
        <p class="article-excerpt">{hero.get('summary_zh','')}</p>
        <div class="article-footer">
          <span class="meta-item">📅 {hero.get('date','')[:10]}</span>
          <span class="read-more">阅读原文 →</span>
        </div>
      </div>
    </a>
    <div class="news-grid">{grid_html}</div>
    <div class="section-label" style="margin-top:6px;">更多动态 · MORE</div>
    <div class="analysis-strip">{analysis_html}</div>
  </div>

  <aside class="sidebar">
    <div class="sidebar-card">
      <div class="sidebar-title">今日来源 · SOURCES</div>
      <div class="company-list">{company_html}</div>
    </div>
    <div class="sidebar-card">
      <div class="sidebar-title">今日数据 · TODAY</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div style="background:rgba(255,255,255,0.02);border-radius:6px;padding:11px;text-align:center;">
          <div style="font-family:var(--mono);font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{len(articles)}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:3px;">今日新闻</div>
        </div>
        <div style="background:rgba(255,255,255,0.02);border-radius:6px;padding:11px;text-align:center;">
          <div style="font-family:var(--mono);font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{len(RSS_SOURCES)}</div>
          <div style="font-size:10px;color:var(--muted);margin-top:3px;">信息来源</div>
        </div>
      </div>
    </div>
    <div class="sidebar-card subscribe-widget">
      <div class="sidebar-title">免费订阅 · SUBSCRIBE</div>
      <p class="subscribe-desc">每天早上7点自动更新。量子科技最重要的内容，中英双语，3分钟读完。</p>
      <input class="email-input" type="email" placeholder="你的邮箱地址">
      <button class="sub-full-btn">免费订阅每日简报</button>
    </div>
  </aside>
</main>

<footer>
  <div style="display:flex;align-items:center;">
    <span class="footer-logo">leQuantum</span>
    <span class="footer-copy">© 2026 · 内容来自 {sources_str}</span>
  </div>
  <div class="footer-links">
    <span class="footer-link">关于</span>
    <span class="footer-link">来源说明</span>
    <span class="footer-link">合作</span>
  </div>
</footer>
</body>
</html>"""


def main():
    today = datetime.date.today().strftime("%Y.%m.%d")
    print(f"\n🦞 LeQuantum 自动更新 · {today}\n")

    print("📡 抓取新闻来源...")
    all_articles = []
    for source in RSS_SOURCES:
        print(f"  → {source['name']}")
        arts = fetch_rss(source)
        all_articles.extend(arts)
        print(f"     获取 {len(arts)} 条")

    print(f"\n📦 共抓取 {len(all_articles)} 条原始新闻")

    if GEMINI_API_KEY:
        print("\n🤖 Gemini AI 整理翻译中...")
        processed = process_with_ai(all_articles)
    else:
        print("\n⚠ 未设置 GEMINI_API_KEY，使用原始数据")
        processed = [{
            "title_zh": a["title"], "title_en": a["title"],
            "summary_zh": a["summary"][:200], "source": a["source"],
            "link": a["link"], "date": a["date"],
            "tags": ["量子科技"], "importance": "medium"
        } for a in all_articles[:NEWS_COUNT]]

    print(f"✅ 整理完成，共 {len(processed)} 条")

    print("\n🌐 生成网页...")
    html = generate_html(processed, today)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ 完成！→ {OUTPUT_FILE}\n")


if __name__ == "__main__":
    main()
