#!/usr/bin/env python3
"""Generate animated SVG cards for a GitHub profile README.

  python generate_cards.py
  STATIC=1 python generate_cards.py  # final frame for screenshots
  python generate_cards.py --refresh-data  # GraphQL refresh; needs GITHUB_TOKEN
"""
from __future__ import annotations
import argparse, base64, io, json, os, re, urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data/contributions.json"
OUT = ROOT / "cards"
FONT_CACHE = ROOT / ".font-cache"
USER = "jamsshid"
STATIC = os.getenv("STATIC", "0").strip().lower() in {"1", "true", "yes"}
NAME = "Jamshid Omonkeldiev"
TAGLINE = "Python Backend Developer building reliable APIs and AI-powered products."
BLUE, BLUE_DARK, BLUE_PALE = "#58A6FF", "#79C0FF", "#172B45"
INK, MUTED, BORDER, WHITE = "#E6EDF3", "#8B949E", "#30363D", "#161B22"
GREEN = "#3FB950"
DARK_BG = "#0D1117"
REPOS = [
    ("E-Commerce API", "ecommerce_api", "REST API with JWT authentication, Stripe checkout and webhooks.", "Django · DRF · PostgreSQL · Stripe · Docker"),
    ("Finance Tracker", "finance-tracker", "Personal finance dashboard with transaction insights and an AI assistant.", "Python · Streamlit · PostgreSQL · Cohere"),
    ("Fids Monro Bot", "fids_monro_bot", "Telegram ordering bot with catalogue, order flow and admin features.", "Python · aiogram · Telegram Bot API"),
]

def e(v): return escape(str(v), {'"': "&quot;"})
def http(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent":"jamsshid-profile-cards"})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read()

def embedded_fonts():
    """Subset Plus Jakarta Sans and JetBrains Mono to Latin glyphs, embed as WOFF2."""
    try:
        from fontTools.ttLib import TTFont
        from fontTools.subset import Options, Subsetter
    except ImportError:
        print("fontTools unavailable; using system font fallbacks.")
        return ""
    FONT_CACHE.mkdir(exist_ok=True)
    result = []
    for family, query, out_name in [
        ("Plus Jakarta Sans", "Plus+Jakarta+Sans:wght@400;500;600;700;800", "plus-jakarta"),
        ("JetBrains Mono", "JetBrains+Mono:wght@400;500;600", "jetbrains-mono"),
    ]:
        try:
            css = http(f"https://fonts.googleapis.com/css2?family={query}&display=swap",
                       {"User-Agent":"Mozilla/5.0"}).decode()
            # Google Fonts no longer consistently includes /* latin */ comments.
            # Select the @font-face block whose Unicode range covers basic Latin.
            face_blocks = re.findall(r"@font-face\s*\{([^}]+)\}", css, flags=re.I)
            latin_block = next(
                (block for block in face_blocks
                 if re.search(r"unicode-range\s*:[^;]*U\+0000-00FF", block, flags=re.I)),
                None,
            )
            if latin_block is None:
                raise RuntimeError("Google Fonts CSS has no identifiable Latin subset")
            urls = re.findall(r"url\((https://[^)]+\.woff2)(?:\?[^)]*)?\)", latin_block)
            if not urls:
                raise RuntimeError("Google Fonts Latin subset has no WOFF2 source")
            source = FONT_CACHE / f"{out_name}-source.woff2"
            source.write_bytes(http(urls[-1]))
            font = TTFont(str(source))
            options = Options(); options.flavor = "woff2"
            subsetter = Subsetter(options=options)
            subsetter.populate(unicodes=list(range(32,127))+[0x2013,0x2014,0x2022,0x00B7,0x2197])
            subsetter.subset(font)
            stream = io.BytesIO(); font.flavor = "woff2"; font.save(stream)
            b64 = base64.b64encode(stream.getvalue()).decode()
            result.append(f'@font-face{{font-family:"{family}";src:url(data:font/woff2;base64,{b64}) format("woff2");font-weight:400 800;font-style:normal}}')
        except Exception as ex:
            print(f"Could not embed {family}: {ex}")
    return "\n".join(result)

def refresh_data():
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token: raise SystemExit("GITHUB_TOKEN is required for --refresh-data")
    query = """query($login:String!){user(login:$login){contributionsCollection{totalCommitContributions restrictedContributionsCount contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday}}}}}}"""
    body = json.dumps({"query":query,"variables":{"login":USER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization":f"Bearer {token}","Content-Type":"application/json","User-Agent":USER})
    with urllib.request.urlopen(req,timeout=30) as response: payload=json.load(response)
    if payload.get("errors") or not payload.get("data",{}).get("user"):
        raise RuntimeError(f"GitHub GraphQL failed: {payload.get('errors')}")
    coll=payload["data"]["user"]["contributionsCollection"]
    cal=coll["contributionCalendar"]
    days=[d for week in cal["weeks"] for d in week["contributionDays"]]
    active=[d for d in days if d["contributionCount"]>0]
    months=defaultdict(int)
    weekday_counts=defaultdict(int)
    for d in days:
        months[d["date"][:7]] += d["contributionCount"]
        weekday_counts[d["weekday"]] += d["contributionCount"]
    today=date.today()
    bydate={date.fromisoformat(d["date"]):d["contributionCount"] for d in days}
    cursor=today if bydate.get(today,0)>0 else today-timedelta(days=1)
    current=0
    while bydate.get(cursor,0)>0:
        current+=1; cursor-=timedelta(days=1)
    longest=run=0
    for d in days:
        run=run+1 if d["contributionCount"]>0 else 0
        longest=max(longest,run)
    weekday_names=["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
    busiest=weekday_names[max(weekday_counts,key=weekday_counts.get)] if weekday_counts else "—"
    best=max(days,key=lambda d:d["contributionCount"],default={"date":"—","contributionCount":0})
    data={
      "updated_at":today.isoformat(),"total_contributions":cal["totalContributions"],
      "total_commit_contributions":coll["totalCommitContributions"],
      "restricted_contributions":coll["restrictedContributionsCount"],
      "active_days":len(active),"current_streak":current,"longest_streak":longest,
      "busiest_weekday":busiest,"busiest_date":best["date"],
      "busiest_date_count":best["contributionCount"],
      "months":[{"month":k,"count":v} for k,v in sorted(months.items())[-12:]],
      "days":[{"date":d["date"],"count":d["contributionCount"],"weekday":d["weekday"]} for d in days],
      "featured_repos":[{"name":n,"slug":slug,"url":f"https://github.com/{USER}/{slug}","description":desc,"stack":stack} for n,slug,desc,stack in REPOS]
    }
    DATA.parent.mkdir(parents=True,exist_ok=True)
    DATA.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    print(f"Updated contribution data: {len(days)} days, {len(months)} months")

def load_data():
    if not DATA.exists(): return {"months":[],"days":[]}
    return json.loads(DATA.read_text(encoding="utf-8"))

def start(w,h,delay,static,fonts):
    motion = "" if static else f"""
      @keyframes rise{{from{{opacity:0;transform:translateY(16px)}}to{{opacity:1;transform:translateY(0)}}}}
      .enter{{opacity:0;animation:rise .8s cubic-bezier(.2,.75,.2,1) {delay:.2f}s both}}
      @keyframes reveal{{to{{stroke-dashoffset:0}}}}
      .line{{stroke-dasharray:1000;stroke-dashoffset:1000;animation:reveal 1.5s ease {delay+.35:.2f}s forwards}}
      @media(prefers-reduced-motion:reduce){{*,*::before,*::after{{animation:none!important;transition:none!important;opacity:1!important;transform:none!important;stroke-dashoffset:0!important}}.smil{{display:none!important}}}}
    """
    if static: motion="@media(prefers-reduced-motion:reduce){*{animation:none!important}}"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
    <style>{fonts}text{{font-family:"Plus Jakarta Sans",Arial,sans-serif}}.mono{{font-family:"JetBrains Mono",monospace}}{motion}</style>'''

def bg(w,h,fill=WHITE):
    return f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="20" fill="{DARK_BG}" stroke="{BORDER}"/>'
def save(name,body):
    OUT.mkdir(exist_ok=True)
    (OUT/name).write_text(body+"</svg>\n",encoding="utf-8")

def hero(fonts,static):
    s=start(1000,238,0,static,fonts)+bg(1000,238,DARK_BG)
    s+='<circle cx="900" cy="22" r="120" fill="#172B45" opacity=".7"/><a xlink:href="https://github.com/jamsshid" target="_blank"><g class="enter">'
    s+=f'<text x="44" y="48" class="mono" font-size="12" letter-spacing="2" fill="{BLUE}">PYTHON BACKEND DEVELOPER · RIGA, LATVIA</text>'
    s+=f'<text x="44" y="115" font-size="42" font-weight="800" fill="{INK}">{e(NAME)}</text>'
    s+=f'<text x="46" y="157" font-size="16" fill="{MUTED}">{e(TAGLINE)}</text>'
    s+=f'<text x="46" y="200" class="mono" font-size="12" fill="{BLUE_DARK}">PYTHON  /  DJANGO  /  FASTAPI  /  POSTGRESQL  /  DOCKER</text></g>'
    s+=f'<circle cx="858" cy="119" r="65" fill="{WHITE}" stroke="{BORDER}" stroke-width="2"/><text x="858" y="138" text-anchor="middle" font-size="54" font-weight="800" fill="{BLUE}">J</text><circle cx="910" cy="171" r="9" fill="{GREEN}" stroke="{WHITE}" stroke-width="4"/>'
    s+="</g></a>"
    save("01-hero.svg",s)

def links(fonts,static):
    items=[("github","GITHUB","github.com/jamsshid","https://github.com/jamsshid","GH"),
           ("linkedin","LINKEDIN","linkedin.com/in/jamsshid","https://linkedin.com/in/jamsshid","in"),
           ("portfolio","PORTFOLIO","Personal website","https://jamsshid.github.io/portfolio","↗")]
    for i,(slug,label,detail,url,mark) in enumerate(items):
        s=start(320,108,.55+i*.18,static,fonts)
        s+=f'<a xlink:href="{url}" target="_blank"><g class="enter"><rect x="1" y="1" width="318" height="106" rx="16" fill="{WHITE}" stroke="{BORDER}"/><rect x="17" y="21" width="42" height="42" rx="12" fill="{BLUE_PALE}"/><text x="38" y="48" text-anchor="middle" font-size="16" font-weight="700" fill="{BLUE}">{mark}</text><text x="76" y="39" class="mono" font-size="11" fill="{BLUE}">{label}</text><text x="76" y="63" font-size="13" fill="{INK}">{detail}</text></g></a>'
        save(f"tile-{slug}.svg",s)

def activity(data,fonts,static):
    s=start(1000,304,1.0,static,fonts)+bg(1000,304)
    s+='<a xlink:href="https://github.com/jamsshid?tab=overview#contributions" target="_blank">'
    s+=f'<text x="30" y="39" font-size="20" font-weight="700" fill="{INK}">Contribution overview · view GitHub contributions ↗</text>'
    stats=[("CURRENT STREAK",f'{data.get("current_streak",0)} days'),("ACTIVE DAYS",data.get("active_days",0)),("BUSIEST DAY",data.get("busiest_weekday","—")),("TOTAL CONTRIBUTIONS",data.get("total_contributions",0))]
    for i,(label,value) in enumerate(stats):
        x=32+i*242
        s+=f'<text x="{x}" y="76" class="mono" font-size="10" fill="{MUTED}">{label}</text><text x="{x}" y="108" font-size="25" font-weight="700" fill="{BLUE}">{e(value)}</text>'
    months=data.get("months",[])[-12:]
    maxv=max([m["count"] for m in months] or [1])
    for i,m in enumerate(months):
        x=42+i*78; h=max(2,104*m["count"]/maxv)
        s+=f'<rect x="{x}" y="{248-h}" width="44" height="{h}" rx="6" fill="{BLUE}" opacity=".9">'
        if not static:
            s+=f'<animate class="smil" attributeName="height" from="0" to="{h:.1f}" dur="1s" begin="{1.3+i*.06:.2f}s" fill="freeze"/>'
        s+='</rect>'
        s+=f'<text x="{x+22}" y="271" text-anchor="middle" class="mono" font-size="9" fill="{MUTED}">{m["month"][5:]}</text>'
    if not months:s+=f'<text x="42" y="210" font-size="14" fill="{MUTED}">Monthly contribution history appears after the first daily refresh.</text>'
    s+=f'<text x="968" y="289" text-anchor="end" class="mono" font-size="9" fill="{MUTED}">UPDATED {data.get("updated_at","—")}</text>'
    s+="</a>"
    save("03-activity.svg",s)

def repo_card(repo,index,fonts,static):
    s=start(1000,152,1.65+index*.38,static,fonts)+bg(1000,152)
    url=repo.get("url",f"https://github.com/{USER}/{repo['slug']}")
    s+=f'<a xlink:href="{url}" target="_blank"><g class="enter"><rect x="26" y="26" width="52" height="52" rx="14" fill="{BLUE_PALE}"/><text x="52" y="61" text-anchor="middle" font-size="23" font-weight="700" fill="{BLUE}">&lt;/&gt;</text><text x="104" y="48" font-size="21" font-weight="700" fill="{INK}">{e(repo["name"])}</text><text x="104" y="78" font-size="14" fill="{MUTED}">{e(repo.get("description",""))}</text><text x="104" y="116" class="mono" font-size="11" fill="{BLUE}">{e(repo.get("stack",""))}</text><text x="952" y="51" text-anchor="end" font-size="12" fill="{BLUE}">OPEN REPOSITORY ↗</text></g></a>'
    save(f"repo-{index+1:02d}.svg",s)

def graph(data,fonts,static):
    days=data.get("days",[])
    width,height=1000,242
    background="#0D1117"
    border="#30363D"
    text="#E6EDF3"
    muted="#8B949E"
    palette=["#161B22","#0E4429","#006D32","#26A641","#39D353"]
    s=start(width,height,3.0,static,fonts)
    s+=f'<a xlink:href="https://github.com/jamsshid?tab=overview#contributions" target="_blank"><rect x="1" y="1" width="{width-2}" height="{height-2}" rx="8" fill="{background}" stroke="{border}"/>'
    total=int(data.get("total_contributions",sum(int(d.get("count",0)) for d in days)))
    s+=f'<text x="30" y="31" font-size="20" fill="{text}">{total} contributions in the last year</text>'
    if days:
        parsed=[(date.fromisoformat(d["date"]),int(d.get("count",0))) for d in days]
        first,last=parsed[0][0],parsed[-1][0]
        weeks=((last-first).days//7)+1
        cell,gap=12,4
        step=cell+gap
        left,top=78,66
        # GitHub's API calendar weeks start on Sunday; the visual rows are Monday-Sunday.
        # Keep the first API date in column zero (Sunday is the bottom row).
        month_cursor=date(first.year,first.month,1)
        previous_x=-100
        while month_cursor<=last:
            col=max(0,(month_cursor-first).days//7)
            x=left+col*step
            label=month_cursor.strftime("%b")
            if x-previous_x>=34:
                s+=f'<text x="{x}" y="53" font-size="13" fill="{text}">{label}</text>'
                previous_x=x
            if month_cursor.month==12:
                month_cursor=date(month_cursor.year+1,1,1)
            else:
                month_cursor=date(month_cursor.year,month_cursor.month+1,1)
        for label,row in [("Mon",0),("Wed",2),("Fri",4)]:
            y=top+row*step+10
            s+=f'<text x="38" y="{y}" font-size="13" fill="{text}">{label}</text>'
        counts={d.isoformat():count for d,count in parsed}
        for col in range(weeks):
            for row in range(7):
                current=first+timedelta(days=col*7+((row+1)%7))
                if current>last:
                    continue
                count=counts.get(current.isoformat(),0)
                level=0 if count==0 else 1 if count<3 else 2 if count<6 else 3 if count<10 else 4
                x=left+col*step
                y=top+row*step
                s+=f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{palette[level]}"><title>{current.isoformat()}: {count} contributions</title></rect>'
        legend_y=top+7*step+9
        s+=f'<text x="30" y="{legend_y}" font-size="12" fill="{muted}">Less</text>'
        legend_x=78
        for i,color in enumerate(palette):
            s+=f'<rect x="{legend_x+i*18}" y="{legend_y-11}" width="12" height="12" rx="3" fill="{color}"/>'
        s+=f'<text x="{legend_x+5*18+5}" y="{legend_y}" font-size="12" fill="{muted}">More</text>'
    else:
        s+=f'<text x="30" y="100" font-size="14" fill="{muted}">Contribution data is not available yet.</text>'
    s+="</a>"
    save("99-contributions.svg",s)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--refresh-data",action="store_true")
    args=parser.parse_args()
    if args.refresh_data:refresh_data()
    data=json.loads(DATA.read_text()) if DATA.exists() else {}
    fonts=embedded_fonts()
    OUT.mkdir(exist_ok=True)
    hero(fonts,STATIC);links(fonts,STATIC);activity(data,fonts,STATIC)
    repos=data.get("featured_repos") or [{"name":n,"slug":slug,"url":f"https://github.com/{USER}/{slug}","description":desc,"stack":stack} for n,slug,desc,stack in REPOS]
    for i,repo in enumerate(repos[:6]):repo_card(repo,i,fonts,STATIC)
    graph(data,fonts,STATIC)
    print(f"Rendered {len(list(OUT.glob('*.svg')))} SVG cards (STATIC={int(STATIC)})")
if __name__=="__main__":main()
