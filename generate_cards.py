#!/usr/bin/env python3
"""Render animated, GitHub-safe SVG profile cards from data/contributions.json."""
from __future__ import annotations
import base64, json, os, re, subprocess
from pathlib import Path
from datetime import date, timedelta
from html import escape

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "contributions.json"
OUT = ROOT / "cards"
STATIC = os.getenv("STATIC", "0") == "1"
BG, PANEL, TEXT, MUTED = "#0d1117", "#161b22", "#e6edf3", "#8b949e"
ACCENT, BLUE, GREEN = "#3670A0", "#58a6ff", "#2ea043"
FONT = "Inter, Segoe UI, Arial, sans-serif"

def load_data():
    if not DATA.exists():
        raise SystemExit("Missing data/contributions.json. Run with GITHUB_TOKEN to refresh it.")
    return json.loads(DATA.read_text())

def font_css():
    source = os.getenv("PROFILE_FONT", "")
    if not source or not Path(source).exists():
        return ""
    target = OUT / "profile-subset.woff2"
    try:
        subprocess.run(["pyftsubset", source, "--output-file=" + str(target),
                        "--flavor=woff2", "--unicodes=U+0000-00FF",
                        "--layout-features=*", "--name-IDs=0,1,2,4,6"],
                       check=True, capture_output=True)
        encoded = base64.b64encode(target.read_bytes()).decode()
        return f"@font-face{{font-family:Profile;src:url(data:font/woff2;base64,{encoded}) format('woff2');font-weight:100 900}}"
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("pyftsubset/font unavailable; using system font stack.")
        return ""

def svg_start(width, height, delay=0):
    motion = "" if STATIC else f"""
      .enter{{opacity:0;transform:translateY(18px);animation:rise .8s cubic-bezier(.2,.8,.2,1) {delay}s forwards}}
      @keyframes rise{{to{{opacity:1;transform:translateY(0)}}}}
      @media(prefers-reduced-motion:reduce){{.enter{{animation:none;opacity:1;transform:none}}}}
    """
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
    <style>{font_css()}{motion} text{{font-family:{FONT}}} .title{{fill:{TEXT};font-size:22px;font-weight:700}} .muted{{fill:{MUTED}}}</style>
    <rect width="100%" height="100%" rx="18" fill="{BG}"/>
    <rect x="1" y="1" width="{width-2}" height="{height-2}" rx="17" fill="none" stroke="#30363d"/>
    '''
def save(name, content):
    (OUT / name).write_text(content + "</svg>\n", encoding="utf-8")

def card_hero(profile):
    s = svg_start(1000, 220, 0) + '<g class="enter">'
    s += f'<text x="42" y="92" class="title" font-size="42">{escape(profile.get("name","Jamshid Omonkeldiev"))}</text>'
    s += f'<text x="44" y="132" fill="{BLUE}" font-size="19">{escape(profile.get("tagline","Python Backend Developer · Backend + AI"))}</text>'
    s += f'<text x="44" y="174" class="muted" font-size="15">{escape(profile.get("location","Riga, Latvia"))}  ·  {escape(profile.get("focus","Building reliable backend systems and AI-powered products"))}</text>'
    portrait = profile.get("portrait_url")
    if portrait:
        s += f'<clipPath id="avatar"><circle cx="885" cy="110" r="67"/></clipPath><image x="{818}" y="43" width="134" height="134" href="{escape(portrait,True)}" clip-path="url(#avatar)" preserveAspectRatio="xMidYMid slice"/>'
        s += '<circle cx="885" cy="110" r="68" fill="none" stroke="#3670A0" stroke-width="3"/>'
    s += "</g>"
    save("01-hero.svg", s)

def card_tiles(profile):
    tiles = profile.get("tiles", [
        {"label":"GitHub","url":"https://github.com/jamsshid","detail":"Code & projects","color":"#3670A0"},
        {"label":"LinkedIn","url":"https://linkedin.com/in/jamsshid","detail":"Professional profile","color":"#0A66C2"},
        {"label":"Instagram","url":"https://instagram.com/jamsshid.o","detail":"Social","color":"#C13584"}])
    s = svg_start(1000, 150, .5)
    for i,t in enumerate(tiles[:3]):
        x = 12 + i*330
        s += f'<a href="{escape(t["url"],True)}"><g class="enter" style="animation-delay:{.5+i*.12}s"><rect x="{x}" y="12" width="325" height="126" rx="14" fill="{PANEL}" stroke="#30363d"/><rect x="{x}" y="12" width="5" height="126" rx="2" fill="{escape(t.get("color",ACCENT),True)}"/><text x="{x+22}" y="61" fill="{TEXT}" font-size="21" font-weight="700">{escape(t["label"])}</text><text x="{x+22}" y="91" class="muted" font-size="14">{escape(t.get("detail","Open profile"))}</text><text x="{x+295}" y="91" fill="{BLUE}" font-size="20">↗</text></g></a>'
    save("02-links.svg",s)

def metrics(data):
    days = data.get("days", [])
    total = sum(int(d.get("count",0)) for d in days)
    active = sum(int(d.get("count",0)) > 0 for d in days)
    counts = {}
    for d in days:
        if d.get("count",0):
            weekday = date.fromisoformat(d["date"]).strftime("%A")
            counts[weekday] = counts.get(weekday,0) + int(d["count"])
    busiest = max(counts, key=counts.get) if counts else "—"
    best = int(data.get("longest_streak",0))
    current = int(data.get("current_streak",0))
    return total, active, busiest, current, best

def card_activity(data):
    days = data.get("days", [])
    months = {}
    for d in days:
        key = d["date"][:7]
        months[key] = months.get(key,0) + int(d.get("count",0))
    items = sorted(months.items())[-12:]
    total, active, busiest, current, best = metrics(data)
    s = svg_start(1000, 310, 1.0) + '<g class="enter"><text x="32" y="48" class="title">Contribution rhythm</text>'
    labels = [("Current streak",str(current)+" days"),("Active days",str(active)),("Busiest day",busiest),("Longest streak",str(best)+" days")]
    for i,(k,v) in enumerate(labels):
        x=32+i*240
        s += f'<text x="{x}" y="88" class="muted" font-size="13">{k}</text><text x="{x}" y="119" fill="{TEXT}" font-size="23" font-weight="700">{escape(v)}</text>'
    maxv=max([v for _,v in items] or [1])
    for i,(month,val) in enumerate(items):
        x=48+i*76
        h=110*val/maxv if maxv else 0
        s += f'<rect x="{x}" y="{250-h}" width="42" height="{h}" rx="5" fill="{ACCENT}"><title>{month}: {val} contributions</title></rect><text x="{x+21}" y="273" text-anchor="middle" class="muted" font-size="10">{month[5:]}</text>'
    s += f'<text x="32" y="294" class="muted" font-size="11">{total} contributions in the available year</text></g>'
    save("03-activity.svg",s)

def card_repo(repo, index):
    name=repo["name"]; desc=repo.get("description","")
    lang=repo.get("language") or "Open source"
    stars=repo.get("stars",0)
    s=svg_start(1000,150,1.5+index*.35)+'<g class="enter">'
    s+=f'<a href="{escape(repo["url"],True)}"><rect x="1" y="1" width="998" height="148" rx="17" fill="{BG}" stroke="#30363d"/><text x="32" y="52" fill="{BLUE}" font-size="23" font-weight="700">{escape(name)}</text><text x="32" y="84" class="muted" font-size="15">{escape(desc[:110])}</text><text x="32" y="119" fill="{ACCENT}" font-size="13">{escape(lang)}  ·  ★ {stars}</text><text x="955" y="80" fill="{BLUE}" font-size="24">↗</text></a></g>'
    save(f"repo-{index+1:02d}.svg",s)

def card_graph(data):
    days=data.get("days",[])
    cells=[]
    if days:
        first=date.fromisoformat(days[0]["date"])
        start=first-timedelta(days=first.weekday())
        bydate={d["date"]:int(d.get("count",0)) for d in days}
        for i in range(53*7):
            dt=start+timedelta(days=i)
            if dt>date.today(): break
            val=bydate.get(dt.isoformat(),0)
            level=0 if val==0 else 1 if val<2 else 2 if val<5 else 3 if val<9 else 4
            x=35+(i//7)*17; y=42+(i%7)*17
            palette=["#161b22","#0e4429","#006d32","#26a641","#39d353"]
            cells.append(f'<rect x="{x}" y="{y}" width="12" height="12" rx="2" fill="{palette[level]}"><title>{dt.isoformat()}: {val}</title></rect>')
    s=svg_start(1000,190,2.1)+'<g class="enter"><text x="32" y="28" class="title">Contribution graph</text>'+''.join(cells)+'</g>'
    save("99-contributions.svg",s)

def main():
    OUT.mkdir(exist_ok=True)
    data=load_data()
    profile=data.get("profile",{})
    card_hero(profile); card_tiles(profile); card_activity(data)
    for i,repo in enumerate(data.get("featured_repos",[])[:6]): card_repo(repo,i)
    card_graph(data)
    print(f"Rendered SVG cards in {OUT} (STATIC={int(STATIC)})")
if __name__=="__main__": main()
