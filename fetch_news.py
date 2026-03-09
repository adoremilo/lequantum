"""
LeQuantum · 量子每天一口
自动抓取量子科技新闻 + Gemini AI整理 + 生成带吉祥物动画的网页
"""

import os, json, datetime, urllib.request, xml.etree.ElementTree as ET, re

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OUTPUT_FILE    = "index.html"
NEWS_COUNT     = 8

RSS_SOURCES = [
    {"name": "Quantum Computing Report", "url": "https://quantumcomputingreport.com/feed/"},
    {"name": "ScienceDaily",             "url": "https://www.sciencedaily.com/rss/matter_energy/quantum_physics.xml"},
    {"name": "The Quantum Insider",      "url": "https://thequantuminsider.com/feed/"},
    {"name": "Phys.org",                 "url": "https://phys.org/rss-feed/physics-news/quantum-physics/"},
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
                articles.append({"source": source["name"], "title": title,
                                  "link": link, "summary": summary,
                                  "date": pubdate[:16] if pubdate else "未知日期"})
    except Exception as e:
        print(f"  ⚠ 抓取失败 {source['name']}: {e}")
    return articles


def call_gemini(prompt):
    if not GEMINI_API_KEY:
        return "[]"
    import time
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0.3, "maxOutputTokens": 5000}}).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            if '429' in str(e) and attempt < 2:
                wait = 30 * (attempt + 1)
                print(f"  ⏳ 限速，等待{wait}秒后重试...")
                time.sleep(wait)
            else:
                raise
    return "[]" 


def process_with_ai(raw_articles):
    articles_text = "\n\n".join([
        f"来源:{a['source']}\n标题:{a['title']}\n摘要:{a['summary']}\n链接:{a['link']}\n日期:{a['date']}"
        for a in raw_articles])
    prompt = f"""你是量子科技新闻编辑。从下面的原始新闻中选出最重要的{NEWS_COUNT}条，整理成JSON。

要求：
1. 优先选最新、影响最大的新闻
2. 英文翻译成通俗易懂的中文，像朋友聊天一样
3. 标签从以下选：量子计算、量子通信、量子传感、材料科学、融资、政策、硬件、算法
4. 重要性：high/medium/low
5. company_radar：从新闻中提取3-5家公司，每家给一句话最新动态（中文）
6. 只返回JSON，不要任何其他文字

格式：
{{
  "articles": [
    {{"title_zh":"中文标题","title_en":"English title","summary_zh":"中文摘要100字内","source":"来源","link":"链接","date":"日期","tags":["标签"],"importance":"high"}}
  ],
  "company_radar": [
    {{"name":"公司名","abbr":"2-4字缩写","update":"最新动态一句话","date":"日期","color":"blue"}}
  ]
}}

color只能从这几个选：blue/purple/gold/red/green

原始新闻：
{articles_text}"""
    try:
        result = call_gemini(prompt)
        result = re.sub(r'^```json\s*|^```\s*|\s*```$', '', result.strip())
        match = re.search(r'\{{.*\}}', result, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return data.get("articles", [])[:NEWS_COUNT], data.get("company_radar", [])
    except Exception as e:
        print(f"  ⚠ AI处理失败: {e}")
    fallback = [{"title_zh": a["title"], "title_en": a["title"], "summary_zh": a["summary"][:200],
                 "source": a["source"], "link": a["link"], "date": a["date"],
                 "tags": ["量子科技"], "importance": "medium"} for a in raw_articles[:NEWS_COUNT]]
    return fallback, []


def get_tag_style(tag):
    return {"量子计算":"tag-blue","量子通信":"tag-purple","量子传感":"tag-gold",
            "材料科学":"tag-gold","融资":"tag-purple","政策":"tag-gold",
            "硬件":"tag-blue","算法":"tag-blue"}.get(tag, "tag-blue")

def get_card_style(importance, i):
    if importance == "high": return ["card-blue","card-purple","card-gold","card-red"][i%4]
    return ["card-blue","card-purple"][i%2]

def company_color(c):
    return {"blue":"rgba(0,212,255,0.1);color:#00d4ff",
            "purple":"rgba(123,79,255,0.1);color:#a78bff",
            "gold":"rgba(240,192,64,0.1);color:#f0c040",
            "red":"rgba(255,80,80,0.1);color:#ff6060",
            "green":"rgba(74,222,128,0.1);color:#4ade80"}.get(c, "rgba(255,255,255,0.06);color:#9ca3af")


def generate_html(articles, company_radar, today):
    hero = articles[0] if articles else {}
    grid_articles     = articles[1:5]
    analysis_articles = articles[5:8]

    # 滚动条（全中文）
    ticker_items = "".join([
        f'<span class="ticker-item">{a.get("title_zh","")} · {a.get("source","")}</span>'
        for a in articles[:6]] * 2)

    hero_tags = "".join([f'<span class="tag {get_tag_style(t)}">{t}</span>' for t in hero.get("tags",[])[:3]])

    grid_html = ""
    for i, a in enumerate(grid_articles):
        tags_html = "".join([f'<span class="tag {get_tag_style(t)}">{t}</span>' for t in a.get("tags",[])[:2]])
        grid_html += f"""<a href="{a.get('link','#')}" target="_blank" style="text-decoration:none;">
          <div class="news-card {get_card_style(a.get('importance','medium'),i)}">
            <div class="source-badge">{a.get('source','')} · {a.get('date','')[:10]}</div>
            <div class="article-tags">{tags_html}</div>
            <h3 class="article-title">{a.get('title_zh','')}</h3>
            <p class="article-excerpt">{a.get('summary_zh','')}</p>
            <div class="article-footer"><span class="meta-item">📅 {a.get('date','')[:10]}</span><span class="read-more">阅读原文 →</span></div>
          </div></a>"""

    analysis_html = ""
    colors = ["var(--accent)","var(--accent2)","var(--gold)"]
    for i, a in enumerate(analysis_articles):
        analysis_html += f"""<a href="{a.get('link','#')}" target="_blank" style="text-decoration:none;">
          <div class="analysis-card">
            <div class="analysis-num" style="color:{colors[i]}">0{i+1}</div>
            <h3 class="analysis-title">{a.get('title_zh','')}</h3>
            <p class="analysis-body">{a.get('summary_zh','')}</p>
            <div style="margin-top:10px;font-family:var(--mono);font-size:10px;color:var(--muted)">{a.get('source','')} · {a.get('date','')[:10]}</div>
          </div></a>"""

    # 公司雷达
    company_html = ""
    if not company_radar:
        seen = set()
        for a in articles[:5]:
            src = a.get("source","")
            if src not in seen:
                seen.add(src)
                company_html += f"""<div class="company-item">
                  <div class="company-logo" style="background:rgba(0,212,255,0.1);color:var(--accent)">{src[0].upper()}</div>
                  <div class="company-info"><div class="company-name">{src}</div>
                  <div class="company-update">{a.get('title_zh','')[:28]}...</div></div>
                  <div class="activity-dot dot-active"></div></div>"""
    else:
        for c in company_radar:
            col = company_color(c.get("color","blue"))
            company_html += f"""<div class="company-item">
              <div class="company-logo" style="background:{col}">{c.get('abbr','?')}</div>
              <div class="company-info"><div class="company-name">{c.get('name','')}</div>
              <div class="company-update">{c.get('update','')} · {c.get('date','')[:10]}</div></div>
              <div class="activity-dot dot-active"></div></div>"""

    sources_str = " · ".join(list(set(a.get("source","") for a in articles[:4])))
    n_high = sum(1 for a in articles if a.get("importance")=="high")
    n_total = len(articles)

    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>乐量子 · 量子每天一口</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;900&family=Space+Mono:wght@400;700&family=Noto+Sans+SC:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{{--black:#0a0a0f;--deep:#0d0d1a;--card:#111120;--border:rgba(100,180,255,0.12);--accent:#00d4ff;--accent2:#7b4fff;--gold:#f0c040;--text:#e8eaf2;--muted:#6b7089;--serif:'Noto Serif SC',serif;--mono:'Space Mono',monospace;--sans:'Noto Sans SC',sans-serif;}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--black);color:var(--text);font-family:var(--sans);min-height:100vh;overflow-x:hidden;}}
a{{color:inherit;}}
body::before{{content:'';position:fixed;inset:0;background-image:linear-gradient(rgba(0,212,255,0.03) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.03) 1px,transparent 1px);background-size:60px 60px;pointer-events:none;z-index:0;}}
body::after{{content:'';position:fixed;top:-200px;right:-200px;width:600px;height:600px;background:radial-gradient(circle,rgba(123,79,255,0.07) 0%,transparent 70%);pointer-events:none;z-index:0;}}

/* ── 动画层 ── */
#intro{{position:fixed;inset:0;z-index:1000;background:#030308;display:flex;flex-direction:column;align-items:center;justify-content:center;transition:opacity 1.5s ease;}}
#intro.fade-out{{opacity:0;pointer-events:none;}}
#intro.gone{{display:none;}}
#anim-canvas{{position:fixed;inset:0;width:100% !important;height:100% !important;}}
.brand-wrap{{position:relative;z-index:2;margin-top:0;display:flex;flex-direction:column;align-items:center;gap:6px;position:fixed;bottom:80px;left:50%;transform:translateX(-50%);}}
.brand-name{{font-family:'Noto Serif SC',serif;font-weight:900;font-size:38px;letter-spacing:0.08em;}}
.brand-name .le{{color:rgba(255,255,255,0.38);}}
.brand-name .q{{background:linear-gradient(135deg,#00d4ff,#7b4fff,#ff6fe8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.brand-sub{{font-family:var(--mono);font-size:11px;letter-spacing:0.4em;color:rgba(255,255,255,0.2);text-transform:uppercase;}}
.skip-btn{{position:fixed;bottom:28px;right:28px;font-family:var(--mono);font-size:10px;color:rgba(255,255,255,0.22);background:transparent;border:1px solid rgba(255,255,255,0.08);padding:6px 14px;border-radius:20px;cursor:pointer;letter-spacing:0.1em;transition:all 0.2s;z-index:1001;}}
.skip-btn:hover{{color:rgba(255,255,255,0.55);border-color:rgba(255,255,255,0.25);}}

/* ── 主内容 ── */
#main-content{{opacity:0;transition:opacity 1.2s ease;}}
#main-content.visible{{opacity:1;}}

header{{position:relative;z-index:10;border-bottom:1px solid var(--border);padding:0 40px;}}
.header-top{{display:flex;align-items:center;justify-content:space-between;padding:20px 0 16px;border-bottom:1px solid var(--border);}}
.logo{{display:flex;align-items:baseline;gap:12px;}}
.logo-zh{{font-family:var(--serif);font-size:26px;font-weight:900;letter-spacing:0.05em;background:linear-gradient(135deg,#fff 0%,var(--accent) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
.logo-en{{font-family:var(--mono);font-size:10px;color:var(--accent);letter-spacing:0.2em;text-transform:uppercase;opacity:0.65;}}
.logo-dot{{width:6px;height:6px;background:var(--accent);border-radius:50%;animation:pulse 2s ease-in-out infinite;margin-bottom:2px;}}
@keyframes pulse{{0%,100%{{opacity:1;transform:scale(1);box-shadow:0 0 0 0 rgba(0,212,255,0.4);}}50%{{opacity:0.8;transform:scale(1.2);box-shadow:0 0 0 6px rgba(0,212,255,0);}}}}
.header-meta{{display:flex;align-items:center;gap:22px;}}
.date-badge{{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:0.1em;}}
.realtime-badge{{font-family:var(--mono);font-size:9px;color:#4ade80;background:rgba(74,222,128,0.08);border:1px solid rgba(74,222,128,0.2);padding:4px 10px;border-radius:4px;letter-spacing:0.1em;display:flex;align-items:center;gap:6px;}}
.realtime-dot{{width:5px;height:5px;background:#4ade80;border-radius:50%;animation:pulse 1.5s ease-in-out infinite;}}
.nav-bar{{display:flex;gap:30px;padding:14px 0;align-items:center;}}
.nav-item{{font-family:var(--sans);font-size:12px;letter-spacing:0.06em;color:var(--muted);cursor:pointer;transition:color 0.2s;font-weight:500;}}
.nav-item.active{{color:var(--accent);border-bottom:1px solid var(--accent);padding-bottom:2px;}}
.nav-right{{margin-left:auto;}}
.subscribe-btn{{background:linear-gradient(135deg,var(--accent2),var(--accent));color:var(--black);border:none;padding:8px 20px;border-radius:6px;font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:0.08em;cursor:pointer;}}

/* 滚动条 */
.ticker-bar{{background:rgba(0,212,255,0.05);border-bottom:1px solid var(--border);padding:10px 40px;display:flex;align-items:center;gap:16px;overflow:hidden;position:relative;z-index:10;}}
.ticker-label{{font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:0.2em;color:var(--accent);white-space:nowrap;background:rgba(0,212,255,0.1);padding:3px 9px;border-radius:3px;border:1px solid rgba(0,212,255,0.2);}}
.ticker-track{{display:flex;gap:55px;animation:ticker 38s linear infinite;white-space:nowrap;}}
.ticker-track:hover{{animation-play-state:paused;}}
@keyframes ticker{{0%{{transform:translateX(0);}}100%{{transform:translateX(-50%);}}}}
.ticker-item{{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:8px;font-family:var(--sans);}}
.ticker-item::before{{content:'◆';color:var(--accent2);font-size:8px;}}

main{{position:relative;z-index:5;max-width:1400px;margin:0 auto;padding:40px;display:grid;grid-template-columns:1fr 340px;gap:40px;}}

.source-badge{{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);font-size:9px;letter-spacing:0.1em;color:#4ade80;background:rgba(74,222,128,0.06);border:1px solid rgba(74,222,128,0.15);padding:2px 8px;border-radius:3px;margin-bottom:10px;}}
.source-badge::before{{content:'✓';}}
.section-label{{font-family:var(--mono);font-size:9px;letter-spacing:0.25em;color:var(--accent);text-transform:uppercase;margin-bottom:20px;display:flex;align-items:center;gap:10px;}}
.section-label::after{{content:'';flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent);}}

.hero-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:24px;cursor:pointer;transition:border-color 0.3s,transform 0.3s;position:relative;display:block;text-decoration:none;}}
.hero-card:hover{{border-color:rgba(0,212,255,0.3);transform:translateY(-2px);}}
.hero-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,var(--accent2),var(--accent));}}
.hero-visual{{height:180px;background:radial-gradient(ellipse at 30% 50%,rgba(123,79,255,0.2) 0%,transparent 60%),radial-gradient(ellipse at 80% 30%,rgba(0,212,255,0.15) 0%,transparent 50%),var(--deep);display:flex;align-items:center;justify-content:center;overflow:hidden;}}
.orbit-wrap{{width:130px;height:130px;position:relative;}}
.orbit{{position:absolute;border:1px solid rgba(0,212,255,0.2);border-radius:50%;top:50%;left:50%;transform:translate(-50%,-50%);}}
.o1{{width:48px;height:48px;animation:spin 4s linear infinite;}}
.o2{{width:84px;height:84px;animation:spin 7s linear infinite reverse;border-color:rgba(123,79,255,0.25);}}
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
.article-title{{font-family:var(--serif);font-size:20px;font-weight:600;line-height:1.6;margin-bottom:8px;color:#fff;}}
.article-title-en{{font-family:var(--mono);font-size:11px;color:var(--muted);margin-bottom:11px;line-height:1.5;}}
.article-excerpt{{font-family:var(--sans);font-size:13px;line-height:1.9;color:rgba(232,234,242,0.65);margin-bottom:16px;font-weight:300;}}
.article-footer{{display:flex;align-items:center;justify-content:space-between;}}
.meta-item{{font-family:var(--mono);font-size:10px;color:var(--muted);}}
.read-more{{font-family:var(--mono);font-size:11px;color:var(--accent);cursor:pointer;display:flex;align-items:center;gap:5px;transition:gap 0.2s;}}
.read-more:hover{{gap:9px;}}

.news-grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;}}
.news-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;cursor:pointer;transition:border-color 0.3s,transform 0.2s;position:relative;overflow:hidden;}}
.news-card:hover{{border-color:rgba(0,212,255,0.25);transform:translateY(-1px);}}
.news-card::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;opacity:0;transition:opacity 0.3s;}}
.news-card:hover::after{{opacity:1;}}
.card-blue::after{{background:linear-gradient(90deg,var(--accent),transparent);}}
.card-purple::after{{background:linear-gradient(90deg,var(--accent2),transparent);}}
.card-gold::after{{background:linear-gradient(90deg,var(--gold),transparent);}}
.card-red::after{{background:linear-gradient(90deg,#ff6060,transparent);}}
.news-card .article-title{{font-size:14px;margin-bottom:7px;}}
.news-card .article-excerpt{{font-size:11px;line-height:1.8;margin-bottom:11px;-webkit-line-clamp:3;display:-webkit-box;-webkit-box-orient:vertical;overflow:hidden;}}

.analysis-strip{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}}
.analysis-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px;cursor:pointer;transition:border-color 0.3s;}}
.analysis-card:hover{{border-color:rgba(0,212,255,0.22);}}
.analysis-num{{font-family:var(--mono);font-size:32px;font-weight:700;line-height:1;margin-bottom:8px;opacity:0.12;}}
.analysis-title{{font-family:var(--serif);font-size:14px;font-weight:600;color:#fff;margin-bottom:7px;line-height:1.5;}}
.analysis-body{{font-family:var(--sans);font-size:11px;color:rgba(232,234,242,0.5);line-height:1.8;font-weight:300;}}

.sidebar{{grid-column:2;display:flex;flex-direction:column;gap:18px;}}
.sidebar-card{{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;}}
.sidebar-title{{font-family:var(--mono);font-size:9px;letter-spacing:0.2em;color:var(--accent);text-transform:uppercase;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border);}}
.company-list{{display:flex;flex-direction:column;gap:9px;}}
.company-item{{display:flex;align-items:center;gap:10px;padding:9px;background:rgba(255,255,255,0.02);border-radius:6px;transition:background 0.2s;}}
.company-item:hover{{background:rgba(255,255,255,0.04);}}
.company-logo{{width:32px;height:32px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-family:var(--mono);font-size:9px;font-weight:700;flex-shrink:0;}}
.company-info{{flex:1;min-width:0;}}
.company-name{{font-family:var(--sans);font-size:11px;font-weight:500;color:var(--text);}}
.company-update{{font-family:var(--sans);font-size:10px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:300;}}
.activity-dot{{width:5px;height:5px;border-radius:50%;flex-shrink:0;}}
.dot-active{{background:#4ade80;box-shadow:0 0 5px #4ade80;animation:pulse 2s ease-in-out infinite;}}
.dot-quiet{{background:var(--muted);}}

.subscribe-widget{{background:linear-gradient(135deg,rgba(123,79,255,0.08),rgba(0,212,255,0.04));border:1px solid rgba(123,79,255,0.18);}}
.subscribe-desc{{font-family:var(--sans);font-size:12px;color:rgba(232,234,242,0.52);line-height:1.8;margin-bottom:12px;font-weight:300;}}
.email-input{{width:100%;background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:6px;padding:9px 12px;color:var(--text);font-family:var(--sans);font-size:12px;margin-bottom:7px;outline:none;}}
.email-input::placeholder{{color:var(--muted);}}
.sub-full-btn{{width:100%;background:linear-gradient(135deg,var(--accent2),var(--accent));color:var(--black);border:none;padding:9px;border-radius:6px;font-family:var(--mono);font-size:11px;font-weight:700;letter-spacing:0.08em;cursor:pointer;}}

footer{{position:relative;z-index:5;border-top:1px solid var(--border);padding:22px 40px;display:flex;align-items:center;justify-content:space-between;margin-top:16px;}}
.footer-logo{{font-family:var(--serif);font-size:16px;font-weight:900;background:linear-gradient(135deg,#fff,var(--accent));-webkit-background-clip:text;-webkit-text-fill-color:transparent;opacity:0.7;}}
.footer-copy{{font-family:var(--mono);font-size:10px;color:var(--muted);margin-left:14px;}}
.footer-links{{display:flex;gap:20px;}}
.footer-link{{font-family:var(--mono);font-size:10px;color:var(--muted);letter-spacing:0.1em;cursor:pointer;}}

@keyframes fadeInUp{{from{{opacity:0;transform:translateY(14px);}}to{{opacity:1;transform:translateY(0);}}}}
.hero-card{{animation:fadeInUp 0.55s ease both;}}
.news-card:nth-child(1){{animation:fadeInUp 0.5s 0.08s ease both;}}
.news-card:nth-child(2){{animation:fadeInUp 0.5s 0.13s ease both;}}
.news-card:nth-child(3){{animation:fadeInUp 0.5s 0.18s ease both;}}
.news-card:nth-child(4){{animation:fadeInUp 0.5s 0.23s ease both;}}

@media(max-width:900px){{
  main{{grid-template-columns:1fr;padding:20px;}}
  .sidebar{{grid-column:1;}}.analysis-strip{{grid-template-columns:1fr;}}
  .news-grid{{grid-template-columns:1fr;}}
  header{{padding:0 20px;}}footer{{padding:16px 20px;flex-direction:column;gap:10px;}}
}}
</style>
</head>
<body>

<!-- ── 动画入场层 ── -->
<div id="intro">
  <canvas id="anim-canvas"></canvas>
  <div class="brand-wrap">
    <div class="brand-name"><span class="le">乐</span><span class="q">量子</span></div>
    <div class="brand-sub">每天一口 · lequantum</div>
  </div>
  <button class="skip-btn" onclick="skipIntro()">跳过 ↓</button>
</div>

<!-- ── 主内容层 ── -->
<div id="main-content">
<header>
  <div class="header-top">
    <div class="logo">
      <div class="logo-dot"></div>
      <div class="logo-zh">乐量子</div>
      <div class="logo-en">LeQuantum</div>
    </div>
    <div class="header-meta">
      <span class="date-badge">{today}</span>
      <div class="realtime-badge"><div class="realtime-dot"></div>真实来源</div>
    </div>
  </div>
  <nav class="nav-bar">
    <span class="nav-item active">今日动态</span>
    <span class="nav-item">深度分析</span>
    <span class="nav-item">公司追踪</span>
    <span class="nav-item">量子比特</span>
    <div class="nav-right"><button class="subscribe-btn">订阅简报 ↗</button></div>
  </nav>
</header>

<div class="ticker-bar">
  <span class="ticker-label">● 实时</span>
  <div class="ticker-track">{ticker_items}</div>
</div>

<main>
  <div>
    <div class="section-label">今日头条</div>
    <a href="{hero.get('link','#')}" target="_blank" class="hero-card">
      <div class="hero-visual">
        <div class="orbit-wrap">
          <div class="orbit o1"><div class="electron"></div></div>
          <div class="orbit o2"></div><div class="orbit o3"></div>
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
    <div class="section-label" style="margin-top:4px;">深度视角</div>
    <div class="analysis-strip">{analysis_html}</div>
  </div>

  <aside class="sidebar">
    <div class="sidebar-card">
      <div class="sidebar-title">公司雷达</div>
      <div class="company-list">{company_html}</div>
    </div>
    <div class="sidebar-card">
      <div class="sidebar-title">今日数据</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <div style="background:rgba(255,255,255,0.02);border-radius:6px;padding:12px;text-align:center;">
          <div style="font-family:var(--mono);font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{n_total}</div>
          <div style="font-family:var(--sans);font-size:10px;color:var(--muted);margin-top:4px;">今日新闻</div>
        </div>
        <div style="background:rgba(255,255,255,0.02);border-radius:6px;padding:12px;text-align:center;">
          <div style="font-family:var(--mono);font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{n_high}</div>
          <div style="font-family:var(--sans);font-size:10px;color:var(--muted);margin-top:4px;">重要事件</div>
        </div>
        <div style="background:rgba(255,255,255,0.02);border-radius:6px;padding:12px;text-align:center;">
          <div style="font-family:var(--mono);font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;">{len(RSS_SOURCES)}</div>
          <div style="font-family:var(--sans);font-size:10px;color:var(--muted);margin-top:4px;">信息来源</div>
        </div>
        <div style="background:rgba(255,255,255,0.02);border-radius:6px;padding:12px;text-align:center;">
          <div style="font-family:var(--mono);font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;">AI</div>
          <div style="font-family:var(--sans);font-size:10px;color:var(--muted);margin-top:4px;">智能整理</div>
        </div>
      </div>
    </div>
    <div class="sidebar-card subscribe-widget">
      <div class="sidebar-title">免费订阅</div>
      <p class="subscribe-desc">每天早上7点自动更新。量子科技最重要的内容，中英双语，3分钟读完。</p>
      <input class="email-input" type="email" placeholder="你的邮箱地址">
      <button class="sub-full-btn">免费订阅每日简报</button>
    </div>
  </aside>
</main>

<footer>
  <div style="display:flex;align-items:center;">
    <span class="footer-logo">乐量子</span>
    <span class="footer-copy">© 2026 · 内容来自 {sources_str}</span>
  </div>
  <div class="footer-links">
    <span class="footer-link">关于</span>
    <span class="footer-link">来源说明</span>
    <span class="footer-link">合作</span>
  </div>
</footer>
</div>

<script>
// ── 动画引擎（Q球吃量子球）──────────────────────────────
const canvas=document.getElementById('anim-canvas');
const ctx=canvas.getContext('2d');
canvas.width=window.innerWidth;
canvas.height=window.innerHeight;
window.addEventListener('resize',()=>{{
  canvas.width=window.innerWidth;
  canvas.height=window.innerHeight;
}});

const lerp=(a,b,t)=>a+(b-a)*t;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const easeOut=t=>1-Math.pow(1-t,4);
const easeIO=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
const spring=(c,t,v,k=0.18,d=0.72)=>{{const nv=(v+(t-c)*k)*d;return[c+nv,nv];}};
const QR=58;

let phase='idle',phaseT=0,frame=0;
let qBY=0,qBVY=0,qSX=1,qSY=1,qSVX=0,qSVY=0,qGlow=0;
let mouth=0.2,mouthV=0,mouthTarget=0.2;
let ballX=0,ballVX=0,ballTarget=0,ballScale=1,ballAlpha=1,ballRot=0;
let isHappy=false,sceneFade=1;
let particles=[],heartPops=[],sparkles=[],starEyes=[],shockwave=null;
let eAngle=0;
let ballInited=false;

const STARS=Array.from({{length:160}},(_,i)=>{{
  return{{x:Math.random()*window.innerWidth,y:Math.random()*window.innerHeight,
    baseR:Math.random()*1.8+0.3,r:0,phase:Math.random()*Math.PI*2,
    drift:{{x:(Math.random()-.5)*0.1,y:(Math.random()-.5)*0.1}},
    hue:Math.random()>0.6?195:Math.random()>0.5?270:45,
    twinkleSpeed:0.02+Math.random()*0.04,
    isShooting:i<3,shootX:Math.random()*window.innerWidth,
    shootY:Math.random()*window.innerHeight*.4,
    shootVX:4+Math.random()*5,shootVY:1+Math.random()*2,
    shootAlpha:0,shootTimer:Math.floor(Math.random()*300),tail:[]}};
}});
const NEBULAE=Array.from({{length:4}},()=>{{
  return{{x:Math.random()*window.innerWidth,y:Math.random()*window.innerHeight,
    r:55+Math.random()*70,hue:[195,270,320,45][Math.floor(Math.random()*4)],
    phase:Math.random()*Math.PI*2,speed:0.003+Math.random()*0.005}};
}});
const ORBITS=[
  {{rx:QR+28,ry:12,tilt:0.4,speed:0.038,ec:'#ffffff',er:3.5}},
  {{rx:QR+20,ry:8,tilt:-0.6,speed:-0.055,ec:'#a78bff',er:2.5}},
  {{rx:QR+35,ry:6,tilt:1.1,speed:0.025,ec:'#00d4ff',er:2}},
];
const BGP=Array.from({{length:45}},()=>{{
  return{{x:Math.random()*window.innerWidth,y:Math.random()*window.innerHeight,
    vx:(Math.random()-.5)*.2,vy:(Math.random()-.5)*.2,
    r:Math.random()*1.4+.3,hue:Math.random()>0.5?195:270,ph:Math.random()*Math.PI*2}};
}});
let finalQScale=0,finalQAlpha=0,finalMouth=0.2,finalMouthV=0,finalMouthTarget=0.2;

function spawnBurst(x,y){{
  const cols=['#00d4ff','#7b4fff','#ff6fe8','#ffffff','#ffe566'];
  for(let i=0;i<26;i++){{const a=(Math.PI*2/26)*i+Math.random()*.4,s=2+Math.random()*5;
    particles.push({{x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s,life:1,decay:.016+Math.random()*.014,r:2+Math.random()*3.5,color:cols[Math.floor(Math.random()*cols.length)]}});}}
}}
function spawnHearts(cx,cy){{for(let i=0;i<7;i++)heartPops.push({{x:cx+(Math.random()-.5)*80,y:cy-20,vy:-1.8-Math.random()*2,vx:(Math.random()-.5)*2,life:1,decay:.009,size:8+Math.random()*11,rot:Math.random()*.6-.3}});}}
function spawnSparkles(cx,cy){{for(let i=0;i<12;i++){{const a=(Math.PI*2/12)*i;sparkles.push({{x:cx,y:cy,tx:cx+Math.cos(a)*(QR+50+Math.random()*18),ty:cy+Math.sin(a)*(QR+50+Math.random()*18),life:1,decay:.022,size:2.5+Math.random()*3}});}}}}
function spawnStarEyes(){{starEyes=[{{angle:0,scale:0}},{{angle:0,scale:0}}];}}
function nextPhase(p){{phase=p;phaseT=0;}}

function updatePhase(QX,QY){{
  phaseT++;
  if(phase==='idle'){{mouthTarget=0.18+.06*Math.sin(frame*.035);if(phaseT>60)nextPhase('approach');}}
  else if(phase==='approach'){{const t=easeIO(clamp(phaseT/55,0,1));ballTarget=lerp(QX+155,QX+QR+18,t);mouthTarget=lerp(0.18,0.62,t);qSX=lerp(1,1.08,t);qSY=lerp(1,0.94,t);if(phaseT>=55)nextPhase('bite');}}
  else if(phase==='bite'){{
    const t=easeOut(clamp(phaseT/12,0,1));mouthTarget=lerp(0.62,0.02,t);
    if(phaseT===1){{qSX=1.28;qSVX=0;qSY=0.76;qSVY=0;qBVY=-5;spawnBurst(QX+QR+5,QY);shockwave={{x:QX,y:QY,r:QR,life:1}};}}
    ballScale=lerp(1,0,clamp(phaseT/10,0,1));ballAlpha=lerp(1,0,clamp(phaseT/8,0,1));
    if(phaseT>=14)nextPhase('chew');
  }}
  else if(phase==='chew'){{mouthTarget=0.12+.08*Math.abs(Math.sin(phaseT*.45));qSX=1+.05*Math.sin(phaseT*.5);qSY=1-.04*Math.sin(phaseT*.5);if(phaseT>35)nextPhase('happy');}}
  else if(phase==='happy'){{
    mouthTarget=0.04;isHappy=true;
    if(phaseT===1){{spawnHearts(QX,QY-QR);spawnStarEyes();spawnSparkles(QX,QY);qBVY=-9;qGlow=1;}}
    if(phaseT>160)nextPhase('fadeout');
  }}
  else if(phase==='fadeout'){{
    sceneFade=clamp(1-(phaseT/110),0,1);isHappy=false;mouthTarget=0.18+.04*Math.sin(frame*.04);
    if(phaseT>=110){{sceneFade=0;nextPhase('starfield');finalQScale=0;finalQAlpha=0;}}
  }}
  else if(phase==='starfield'){{
    if(phaseT<90){{finalQScale=easeOut(clamp(phaseT/90,0,1));finalQAlpha=clamp(phaseT/90,0,1);}}
    finalMouthTarget=0.18+.07*Math.sin(frame*.022);
    if(phaseT===150)showMainContent();
  }}
}}

function updatePhysics(QX,QY){{
  [mouth,mouthV]=spring(mouth,mouthTarget,mouthV,0.22,0.68);
  [finalMouth,finalMouthV]=spring(finalMouth,finalMouthTarget,finalMouthV,0.12,0.72);
  qBVY+=0.55;qBY+=qBVY;
  if(qBY>0){{qBY=0;qBVY*=-0.42;if(Math.abs(qBVY)<0.5)qBVY=0;}}
  if(qBY>=-1&&Math.abs(qBVY)>1){{qSX=1.18;qSY=0.84;}}
  [qSX,qSVX]=spring(qSX,1,qSVX,0.15,0.65);[qSY,qSVY]=spring(qSY,1,qSVY,0.15,0.65);
  [ballX,ballVX]=spring(ballX,ballTarget,ballVX,0.14,0.78);
  ballRot+=0.04;qGlow=Math.max(0,qGlow-.006);eAngle+=0.01;
  if(shockwave){{shockwave.r+=4;shockwave.life-=.07;if(shockwave.life<=0)shockwave=null;}}
  starEyes.forEach(s=>{{s.scale=Math.min(s.scale+.07,1);s.angle+=.07;}});
  particles=particles.filter(p=>p.life>0);particles.forEach(p=>{{p.x+=p.vx;p.y+=p.vy;p.vx*=.91;p.vy*=.91;p.life-=p.decay;}});
  heartPops=heartPops.filter(p=>p.life>0);heartPops.forEach(p=>{{p.x+=p.vx;p.y+=p.vy;p.vy+=.025;p.life-=p.decay;}});
  sparkles=sparkles.filter(p=>p.life>0);sparkles.forEach(p=>{{p.x=lerp(p.x,p.tx,.07);p.y=lerp(p.y,p.ty,.07);p.life-=p.decay;}});
}}

function updateStars(W,H){{
  STARS.forEach(s=>{{
    s.phase+=s.twinkleSpeed;s.x+=s.drift.x;s.y+=s.drift.y;
    if(s.x<-5)s.x=W+5;if(s.x>W+5)s.x=-5;if(s.y<-5)s.y=H+5;if(s.y>H+5)s.y=-5;
    s.r=s.baseR*(0.5+0.5*Math.abs(Math.sin(s.phase)));
    if(s.isShooting){{
      s.shootTimer--;
      if(s.shootTimer<=0){{s.shootX=-10;s.shootY=Math.random()*H*.4;s.shootVX=4+Math.random()*6;s.shootVY=1+Math.random()*2.5;s.shootAlpha=1;s.tail=[];s.shootTimer=180+Math.random()*280;}}
      if(s.shootAlpha>0){{s.tail.unshift({{x:s.shootX,y:s.shootY}});if(s.tail.length>14)s.tail.pop();s.shootX+=s.shootVX;s.shootY+=s.shootVY;s.shootAlpha-=.028;if(s.shootX>W+50||s.shootAlpha<=0)s.shootAlpha=0;}}
    }}
  }});
  NEBULAE.forEach(n=>{{n.phase+=n.speed;}});
}}

function drawBG(W,H,sf){{
  const bg=ctx.createRadialGradient(W/2,H/2,0,W/2,H/2,W*.85);
  if(sf){{bg.addColorStop(0,'#080820');bg.addColorStop(.5,'#050510');bg.addColorStop(1,'#030308');}}
  else{{bg.addColorStop(0,'#0a0a1a');bg.addColorStop(.5,'#060610');bg.addColorStop(1,'#030308');}}
  ctx.fillStyle=bg;ctx.fillRect(0,0,W,H);
  if(!sf){{BGP.forEach(p=>{{p.x+=p.vx;p.y+=p.vy;p.ph+=.02;if(p.x<0)p.x=W;if(p.x>W)p.x=0;if(p.y<0)p.y=H;if(p.y>H)p.y=0;ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle=`hsla(${{p.hue}},80%,70%,${{.1+.07*Math.sin(p.ph)}})`;ctx.fill();}});}}
  ctx.save();ctx.globalAlpha=sf?.01:.02;ctx.strokeStyle='#00d4ff';ctx.lineWidth=.5;
  for(let x=0;x<W;x+=40){{ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,H);ctx.stroke();}}
  for(let y=0;y<H;y+=40){{ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}}
  ctx.restore();
}}

function drawStarfield(W,H){{
  NEBULAE.forEach(n=>{{const g=ctx.createRadialGradient(n.x,n.y,0,n.x,n.y,n.r*(1+.15*Math.sin(n.phase)));g.addColorStop(0,`hsla(${{n.hue}},70%,60%,0.035)`);g.addColorStop(1,'rgba(0,0,0,0)');ctx.beginPath();ctx.arc(n.x,n.y,n.r*1.5,0,Math.PI*2);ctx.fillStyle=g;ctx.fill();}});
  STARS.forEach(s=>{{
    const alpha=.15+.5*Math.abs(Math.sin(s.phase));
    ctx.beginPath();ctx.arc(s.x,s.y,s.r,0,Math.PI*2);ctx.fillStyle=`hsla(${{s.hue}},80%,85%,${{alpha}})`;
    if(s.r>1.2){{ctx.shadowColor=`hsl(${{s.hue}},80%,80%)`;ctx.shadowBlur=s.r*4;}}
    ctx.fill();ctx.shadowBlur=0;
    if(s.baseR>1.5){{const len=s.r*6;ctx.save();ctx.globalAlpha=alpha*.45;ctx.strokeStyle=`hsl(${{s.hue}},80%,85%)`;ctx.lineWidth=.5;ctx.beginPath();ctx.moveTo(s.x-len,s.y);ctx.lineTo(s.x+len,s.y);ctx.stroke();ctx.beginPath();ctx.moveTo(s.x,s.y-len);ctx.lineTo(s.x,s.y+len);ctx.stroke();ctx.restore();}}
    if(s.isShooting&&s.shootAlpha>0){{ctx.save();s.tail.forEach((t,i)=>{{ctx.beginPath();ctx.arc(t.x,t.y,1.4*(1-i/s.tail.length),0,Math.PI*2);ctx.fillStyle=`rgba(255,255,255,${{s.shootAlpha*(1-i/s.tail.length)*.7}})`;ctx.fill();}});ctx.beginPath();ctx.arc(s.shootX,s.shootY,2.2,0,Math.PI*2);ctx.fillStyle=`rgba(255,255,255,${{s.shootAlpha}})`;ctx.shadowColor='#fff';ctx.shadowBlur=7;ctx.fill();ctx.shadowBlur=0;ctx.restore();}}
  }});
}}

function drawOrbits(cx,cy){{
  ORBITS.forEach((o,i)=>{{
    ctx.save();ctx.translate(cx,cy);ctx.rotate(o.tilt);
    ctx.beginPath();ctx.ellipse(0,0,o.rx,o.ry,0,0,Math.PI*2);
    ctx.strokeStyle=i===0?'rgba(0,212,255,0.18)':i===1?'rgba(123,79,255,0.15)':'rgba(0,212,255,0.1)';ctx.lineWidth=1;ctx.stroke();
    const ea=eAngle*(i%2===0?1:-1)*(1+i*.3),ex=o.rx*Math.cos(ea),ey=o.ry*Math.sin(ea);
    for(let t=1;t<=5;t++){{const ta=ea-t*.15;ctx.beginPath();ctx.arc(o.rx*Math.cos(ta),o.ry*Math.sin(ta),o.er*(1-t/6),0,Math.PI*2);ctx.globalAlpha=.3*(1-t/7);ctx.fillStyle=o.ec;ctx.fill();}}
    ctx.globalAlpha=1;ctx.beginPath();ctx.arc(ex,ey,o.er,0,Math.PI*2);ctx.fillStyle=o.ec;ctx.shadowColor=o.ec;ctx.shadowBlur=10;ctx.fill();ctx.shadowBlur=0;ctx.restore();
  }});
}}

function drawQ(cx,cy,mA,happy,sc=1,al=1){{
  ctx.save();ctx.globalAlpha=al;ctx.translate(cx,cy);ctx.scale(qSX*sc,qSY*sc);
  const og=ctx.createRadialGradient(0,0,QR*.5,0,0,QR*2.2);
  og.addColorStop(0,`rgba(0,212,255,${{.07+qGlow*.18}})`);og.addColorStop(.45,`rgba(123,79,255,${{.03+qGlow*.08}})`);og.addColorStop(1,'rgba(0,0,0,0)');
  ctx.beginPath();ctx.arc(0,0,QR*2.2,0,Math.PI*2);ctx.fillStyle=og;ctx.fill();
  const g=ctx.createRadialGradient(-QR*.3,-QR*.3,QR*.05,0,0,QR);
  g.addColorStop(0,'#9ef8ff');g.addColorStop(.2,'#00d4ff');g.addColorStop(.55,'#0088cc');g.addColorStop(.85,'#003d99');g.addColorStop(1,'#001133');
  ctx.beginPath();
  if(mA>0.02){{ctx.moveTo(0,0);ctx.arc(0,0,QR,mA,Math.PI*2-mA);ctx.lineTo(0,0);}}else ctx.arc(0,0,QR,0,Math.PI*2);
  ctx.fillStyle=g;ctx.shadowColor='#00d4ff';ctx.shadowBlur=18+qGlow*32;ctx.fill();ctx.shadowBlur=0;
  const fr=ctx.createRadialGradient(-QR*.25,-QR*.3,0,-QR*.1,-QR*.15,QR*.55);
  fr.addColorStop(0,'rgba(255,255,255,0.36)');fr.addColorStop(1,'rgba(255,255,255,0)');
  ctx.beginPath();ctx.arc(0,0,QR,0,Math.PI*2);ctx.fillStyle=fr;ctx.fill();
  for(let r=1;r<=3;r++){{ctx.beginPath();ctx.arc(0,0,QR*(r/4),0,Math.PI*2);ctx.strokeStyle=`rgba(255,255,255,${{.04}})`;ctx.lineWidth=.8;ctx.stroke();}}
  ctx.beginPath();ctx.arc(0,0,QR,0,Math.PI*2);
  const rim=ctx.createLinearGradient(-QR,-QR,QR,QR);rim.addColorStop(0,'rgba(255,255,255,0.26)');rim.addColorStop(.5,'rgba(0,212,255,0.14)');rim.addColorStop(1,'rgba(0,0,0,0)');
  ctx.strokeStyle=rim;ctx.lineWidth=2;ctx.stroke();
  const eyeOX=15,eyeOY=happy?-9:-13;
  if(happy&&starEyes.length===2){{
    [[-eyeOX,eyeOY],[eyeOX,eyeOY]].forEach(([ex,ey],i)=>{{
      const se=starEyes[i];if(!se)return;ctx.save();ctx.translate(ex,ey);ctx.scale(se.scale,se.scale);ctx.rotate(se.angle);
      ctx.beginPath();for(let p=0;p<5;p++){{const a=(Math.PI*2/5)*p-Math.PI/2,ai=a+Math.PI/5;p===0?ctx.moveTo(Math.cos(a)*8,Math.sin(a)*8):ctx.lineTo(Math.cos(a)*8,Math.sin(a)*8);ctx.lineTo(Math.cos(ai)*3.5,Math.sin(ai)*3.5);}}
      ctx.closePath();ctx.fillStyle='#ffe566';ctx.shadowColor='#ffe566';ctx.shadowBlur=10;ctx.fill();ctx.shadowBlur=0;ctx.restore();
    }});
    ctx.beginPath();ctx.ellipse(-eyeOX+2,eyeOY+13,8,4.5,0,0,Math.PI*2);ctx.fillStyle='rgba(255,140,140,0.28)';ctx.fill();
    ctx.beginPath();ctx.ellipse(eyeOX-2,eyeOY+13,8,4.5,0,0,Math.PI*2);ctx.fillStyle='rgba(255,140,140,0.28)';ctx.fill();
  }} else {{
    [-eyeOX,eyeOX].forEach(ex=>{{
      ctx.beginPath();ctx.arc(ex,eyeOY,7,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();
      const px=ex+mA*.7;ctx.beginPath();ctx.arc(px,eyeOY,4.2,0,Math.PI*2);ctx.fillStyle='#0a1a2e';ctx.fill();
      ctx.beginPath();ctx.arc(px+1.4,eyeOY-1.4,1.4,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();
    }});
  }}
  ctx.restore();
}}

function drawBall(){{
  if(ballAlpha<=0.01)return;
  ctx.save();ctx.globalAlpha=ballAlpha;ctx.translate(ballX,ballY_ball);ctx.rotate(ballRot);ctx.scale(ballScale,ballScale);
  const gw=ctx.createRadialGradient(0,0,0,0,0,26);gw.addColorStop(0,'rgba(123,79,255,0.5)');gw.addColorStop(1,'rgba(0,0,0,0)');
  ctx.beginPath();ctx.arc(0,0,26,0,Math.PI*2);ctx.fillStyle=gw;ctx.fill();
  const g=ctx.createRadialGradient(-5,-5,2,0,0,17);g.addColorStop(0,'#e0b8ff');g.addColorStop(.4,'#9b59ff');g.addColorStop(1,'#2a0080');
  ctx.beginPath();ctx.arc(0,0,17,0,Math.PI*2);ctx.fillStyle=g;ctx.shadowColor='#7b4fff';ctx.shadowBlur=18;ctx.fill();ctx.shadowBlur=0;
  ctx.fillStyle='rgba(255,255,255,0.92)';ctx.font='bold 16px serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText('Q',0,1);
  ctx.restore();
}}

function drawFX(QX,QY){{
  particles.forEach(p=>{{ctx.save();ctx.globalAlpha=p.life;ctx.beginPath();ctx.arc(p.x,p.y,p.r*p.life,0,Math.PI*2);ctx.fillStyle=p.color;ctx.shadowColor=p.color;ctx.shadowBlur=7;ctx.fill();ctx.shadowBlur=0;ctx.restore();}});
  heartPops.forEach(p=>{{ctx.save();ctx.globalAlpha=p.life;ctx.translate(p.x,p.y);ctx.rotate(p.rot);ctx.scale(p.size/18,p.size/18);ctx.beginPath();ctx.moveTo(0,-5);ctx.bezierCurveTo(5,-10,11,-6,11,0);ctx.bezierCurveTo(11,6,0,13,0,17);ctx.bezierCurveTo(0,13,-11,6,-11,0);ctx.bezierCurveTo(-11,-6,-5,-10,0,-5);ctx.fillStyle='#ff6b9d';ctx.shadowColor='#ff6b9d';ctx.shadowBlur=9;ctx.fill();ctx.shadowBlur=0;ctx.restore();}});
  sparkles.forEach(p=>{{ctx.save();ctx.globalAlpha=p.life*.9;ctx.translate(p.x,p.y);ctx.beginPath();for(let i=0;i<4;i++){{const a=(Math.PI/2)*i,ai=a+Math.PI/4;i===0?ctx.moveTo(Math.cos(a)*p.size,Math.sin(a)*p.size):ctx.lineTo(Math.cos(a)*p.size,Math.sin(a)*p.size);ctx.lineTo(Math.cos(ai)*p.size*.3,Math.sin(ai)*p.size*.3);}}ctx.closePath();ctx.fillStyle='#ffe566';ctx.shadowColor='#ffe566';ctx.shadowBlur=7;ctx.fill();ctx.shadowBlur=0;ctx.restore();}});
  if(shockwave){{ctx.beginPath();ctx.arc(shockwave.x,shockwave.y+qBY,shockwave.r,0,Math.PI*2);ctx.strokeStyle=`rgba(0,212,255,${{shockwave.life*.55}})`;ctx.lineWidth=3*shockwave.life;ctx.stroke();}}
}}

let ballY_ball=0;

function showMainContent(){{
  document.getElementById('intro').classList.add('fade-out');
  document.getElementById('main-content').classList.add('visible');
  setTimeout(()=>document.getElementById('intro').classList.add('gone'),1600);
}}
function skipIntro(){{showMainContent();}}

function loop(){{
  frame++;
  const W=canvas.width,H=canvas.height;
  const QX=W/2-60,QY=H/2;
  ballY_ball=QY;

  // 第一帧初始化球的位置
  if(frame===1){{ballX=QX+155;ballTarget=QX+155;}}

  updatePhase(QX,QY);
  updatePhysics(QX,QY);
  updateStars(W,H);

  ctx.clearRect(0,0,W,H);

  if(phase==='starfield'){{
    drawBG(W,H,true);drawStarfield(W,H);
    if(finalQAlpha>0.01){{
      ctx.save();ctx.globalAlpha=finalQAlpha*.7;drawOrbits(W/2,H/2);ctx.restore();
      qSX=1+.01*Math.sin(frame*.03);qSY=1-.008*Math.sin(frame*.03);
      drawQ(W/2,H/2,finalMouth,false,finalQScale,finalQAlpha);
    }}
  }} else {{
    drawBG(W,H,false);
    if(phase==='fadeout'){{ctx.save();ctx.globalAlpha=1-sceneFade;ctx.fillStyle='#030308';ctx.fillRect(0,0,W,H);ctx.restore();ctx.save();ctx.globalAlpha=sceneFade;}}
    const cy=QY+qBY;
    drawOrbits(QX,cy);drawFX(QX,QY);drawBall();
    drawQ(QX,cy,mouth,isHappy);drawFX(QX,QY);
    if(phase==='fadeout')ctx.restore();
  }}
  requestAnimationFrame(loop);
}}
loop();
</script>
</body>
</html>"""


def main():
    today = datetime.date.today().strftime("%Y年%m月%d日")
    print(f"\n🦞 乐量子 自动更新 · {today}\n")

    print("📡 抓取新闻...")
    all_articles = []
    for source in RSS_SOURCES:
        print(f"  → {source['name']}")
        arts = fetch_rss(source)
        all_articles.extend(arts)
        print(f"     获取 {len(arts)} 条")

    print(f"\n📦 共抓取 {len(all_articles)} 条")

    if GEMINI_API_KEY:
        print("\n🤖 Gemini AI 整理中...")
        articles, company_radar = process_with_ai(all_articles)
    else:
        print("\n⚠ 未设置 GEMINI_API_KEY")
        articles = [{"title_zh":a["title"],"title_en":a["title"],"summary_zh":a["summary"][:200],
                     "source":a["source"],"link":a["link"],"date":a["date"],
                     "tags":["量子科技"],"importance":"medium"} for a in all_articles[:NEWS_COUNT]]
        company_radar = []

    print(f"✅ 整理完成，共 {len(articles)} 条")
    print("\n🌐 生成网页...")
    html = generate_html(articles, company_radar, today)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 完成！→ {OUTPUT_FILE}\n")

if __name__ == "__main__":
    main()
