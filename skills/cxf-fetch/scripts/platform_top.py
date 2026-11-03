#!/usr/bin/env python3
"""平台抓取：博主主页 -> 按点赞/播放排序的 Top N 作品清单 -> 每条逐字稿（Markdown 存进知识库）。
免费、默认免登录；抖音签名代码摘自 Evil0ctal/Douyin_TikTok_Download_API（Apache-2.0，见 dysign/）。

  python platform_top.py doctor                         # 检查依赖
  python platform_top.py login                          # 可选：弹出浏览器扫码登录抖音（扫全部作品才需要）
  python platform_top.py run "<链接或分享文案>" --out "知识库目录" [--since 180d --sort likes --top 10 --with-comments 30]
      · 主页链接 -> 时间范围内按 sort 取前 top 条：清单 + 每条逐字稿
      · 单条视频链接 -> 只抓这一条（加 --author 则改为调研该视频作者的主页）
  python platform_top.py list  "<主页链接>" ...          # 只出清单不转写
  python platform_top.py video "<视频链接>" ...          # 强制单条
  python platform_top.py transcribe "<目录>/works.json"  # 给清单补逐字稿（可断点续跑）
  python platform_top.py file  "本地视频或音频路径" --out "目录"   # 视频号等抓不到时：用户自己下载后转写

退出码：0 成功；2 依赖缺失；3 平台拒绝（需要用户登录/过验证码/换网络）；4 链接无法识别；1 其他错误。
最后一行 stdout 永远是一行 JSON，智能体读它判断结果。
"""
import argparse, datetime, json, os, random, re, shutil, subprocess, sys, time, urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
HOME = Path(os.environ.get("PLATFORM_SCRAPER_HOME", Path.home() / ".platform-scraper"))
PC_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
MOB_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
TZ8 = datetime.timezone(datetime.timedelta(hours=8))
PLAT_CN = {"douyin": "抖音", "bilibili": "B站", "youtube": "YouTube", "local": "本地"}


class Blocked(Exception):
    """平台拒绝：需要登录、验证码或换网络。"""


def log(*a):
    print("[platform-scraper]", *a, file=sys.stderr, flush=True)


def done(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False))
    sys.exit(code)


def ts(epoch):
    return datetime.datetime.fromtimestamp(int(epoch), TZ8).strftime("%Y-%m-%d %H:%M") if epoch else None


def safe_name(s, n=40):
    s = re.sub(r"#\S+", "", s or "").strip()
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", s).strip() or "untitled"
    return s[:n].strip()


def extract_url(text):
    m = re.search(r"https?://[^\s\u4e00-\u9fff，。！？、；：“”‘’（）【】《》]+", text)
    return m.group(0).rstrip(".,;:!?)]}'\"") if m else None


def httpx_client(**kw):
    import httpx
    return httpx.Client(follow_redirects=True, timeout=30, **kw)


# ============================================================ 抖音
def douyin_cookies(refresh=False, cookie_file=None):
    """优先用户提供的 cookie（登录态，可选）；否则用本机浏览器无头打开 douyin.com 领一份游客 cookie，缓存 6 小时。"""
    if cookie_file:
        raw = Path(cookie_file).read_text(encoding="utf-8").strip()
        if raw.startswith("{"):
            return json.loads(raw)
        return dict(p.strip().split("=", 1) for p in raw.split(";") if "=" in p)
    HOME.mkdir(parents=True, exist_ok=True)
    lf = HOME / "douyin_login_cookies.json"
    if lf.exists() and not refresh:
        return json.loads(lf.read_text())
    f = HOME / "douyin_guest_cookies.json"
    if f.exists() and not refresh and time.time() - f.stat().st_mtime < 6 * 3600:
        return json.loads(f.read_text())
    log("领取抖音游客 cookie（后台打开一次浏览器，约 15 秒）…")
    import asyncio
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise SystemExit("缺少 playwright：pip install playwright（无需下载浏览器，会用本机 Chrome/Edge）")

    async def mint():
        async with async_playwright() as p:
            b, err = None, None
            for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {"executable_path": "/usr/bin/google-chrome"}, {}):
                if kw.get("executable_path") and not os.path.exists(kw["executable_path"]):
                    continue
                try:
                    b = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"], **kw)
                    break
                except Exception as e:
                    err = e
            if not b:
                raise SystemExit(f"找不到可用浏览器（需要 Chrome 或 Edge，或运行 playwright install chromium）：{err}")
            ctx = await b.new_context(user_agent=PC_UA, locale="zh-CN", viewport={"width": 1366, "height": 800})
            page = await ctx.new_page()
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(10000)
            ck = {c["name"]: c["value"] for c in await ctx.cookies() if "douyin" in c["domain"] and c["name"]}
            await b.close()
            return ck
    ck = asyncio.run(mint())
    f.write_text(json.dumps(ck))
    try:
        os.chmod(f, 0o600)
    except Exception:
        pass
    return ck


def douyin_login(timeout_s=180):
    """打开一个看得见的浏览器窗口，用户用抖音 App 扫码登录；登录态存本机，之后脚本自动使用。"""
    import asyncio
    from playwright.async_api import async_playwright
    HOME.mkdir(parents=True, exist_ok=True)
    async def run():
        async with async_playwright() as p:
            ctx, err = None, None
            for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
                try:
                    ctx = await p.chromium.launch_persistent_context(str(HOME / "douyin_browser"), headless=False, locale="zh-CN",
                                                                     args=["--disable-blink-features=AutomationControlled"], **kw)
                    break
                except Exception as e:
                    err = e
            if not ctx:
                raise SystemExit(f"打不开浏览器：{err}")
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
            log(f"请在弹出的浏览器里用抖音 App 扫码登录（{timeout_s} 秒内）…")
            for _ in range(timeout_s // 3):
                ck = {c["name"]: c["value"] for c in await ctx.cookies() if "douyin" in c["domain"]}
                if ck.get("sessionid") or ck.get("sessionid_ss"):
                    await page.wait_for_timeout(5000)
                    ck = {c["name"]: c["value"] for c in await ctx.cookies() if "douyin" in c["domain"]}
                    await ctx.close()
                    return ck
                await page.wait_for_timeout(3000)
            await ctx.close()
            return None
    ck = asyncio.run(run())
    if not ck:
        return False
    f = HOME / "douyin_login_cookies.json"
    f.write_text(json.dumps(ck))
    try:
        os.chmod(f, 0o600)
    except Exception:
        pass
    return True


def douyin_get(path, extra, ck, referer="https://www.douyin.com/"):
    from dysign.abogus import ABogus
    from dysign import websign
    p = {"device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web", "pc_client_type": "1",
         "version_code": "290100", "version_name": "29.1.0", "cookie_enabled": "true",
         "screen_width": "1920", "screen_height": "1080", "browser_language": "zh-CN",
         "browser_platform": "Win32", "browser_name": "Chrome", "browser_version": "130.0.0.0",
         "browser_online": "true", "engine_name": "Blink", "engine_version": "130.0.0.0",
         "os_name": "Windows", "os_version": "10", "cpu_core_num": "12", "device_memory": "8",
         "platform": "PC", "downlink": "10", "effective_type": "4g", "round_trip_time": "0",
         "update_version_code": "170400", **extra, "msToken": ck.get("msToken", "")}
    q = urllib.parse.urlencode(p)
    q += "&a_bogus=" + urllib.parse.quote(ABogus(PC_UA).get_value(q), safe="")
    pairs = [tuple(urllib.parse.unquote_plus(x) for x in part.split("=", 1)) for part in q.split("&")]
    if ck.get("s_v_web_id"):
        pairs += [("verifyFp", ck["s_v_web_id"]), ("fp", ck["s_v_web_id"])]
    uifid = websign.pick_uifid(ck)
    sq = websign.sign(pairs, uifid)[0] if uifid else websign.encode_pairs(pairs)
    with httpx_client() as c:
        r = c.get("https://www.douyin.com" + path + "?" + sq,
                  headers={"User-Agent": PC_UA, "Referer": referer, "Cookie": "; ".join(f"{k}={v}" for k, v in ck.items())})
    try:
        return r.json()
    except Exception:
        return {"_http": r.status_code, "_text": r.text[:200]}


def douyin_call(path, extra, args, ok, referer="https://www.douyin.com/"):
    for attempt in range(2):
        ck = douyin_cookies(refresh=attempt > 0 and not args.cookies, cookie_file=args.cookies)
        j = douyin_get(path, extra, ck, referer)
        if ok(j):
            return j
        log(f"抖音接口没给数据（{str(j)[:160]}），{'换一份游客 cookie 重试' if attempt == 0 else '放弃'}")
        if args.cookies:
            break
    raise Blocked("抖音接口拒绝（可能是风控/签名过期/需要登录）。可让用户提供登录后的 cookie（--cookies），或稍后再试。")


def douyin_item(a):
    st, v = a.get("statistics") or {}, a.get("video") or {}
    return {"platform": "douyin", "id": a["aweme_id"], "url": f"https://www.douyin.com/video/{a['aweme_id']}",
            "title": (a.get("item_title") or a.get("preview_title") or re.split(r"\s#|^#", a.get("desc") or "")[0]).strip().splitlines()[0] if (a.get("item_title") or a.get("preview_title") or (a.get("desc") or "").strip()) else "（无标题）",
            "desc": a.get("desc"), "publish_time": ts(a.get("create_time")), "epoch": a.get("create_time"),
            "duration_sec": round((v.get("duration") or a.get("duration") or 0) / 1000, 1),
            "likes": st.get("digg_count"), "comments": st.get("comment_count"), "collects": st.get("collect_count"),
            "shares": st.get("share_count"), "plays": st.get("play_count") or None,
            "is_top": bool(a.get("is_top")), "type": "图文" if a.get("images") else "视频",
            "media_urls": ((v.get("play_addr") or {}).get("url_list") or []) if not a.get("images") else []}


def douyin_list(url, args):
    final = url
    if re.search(r"v\.douyin\.com|iesdouyin\.com", url):
        with httpx_client() as c:
            final = str(c.get(url, headers={"User-Agent": MOB_UA}).url)
    m = re.search(r"/user/(MS4w[\w\-.]+)", final) or re.search(r"sec_uid=(MS4w[\w\-.]+)", final)
    sec = m.group(1) if m else None
    if not sec:
        vm = re.search(r"/(?:video|note|slides)/(\d+)", final) or re.search(r"modal_id=(\d+)", final)
        if not vm:
            raise ValueError(f"认不出抖音主页或作品：{final}")
        log("给的是单条作品，先取作者主页")
        d = douyin_call("/aweme/v1/web/aweme/detail/", {"aweme_id": vm.group(1)}, args, lambda j: j.get("aweme_detail"))
        sec = d["aweme_detail"]["author"]["sec_uid"]
    items, cursor, author, partial = [], "0", {}, None
    seen = set()
    while len(items) < args.max_items:
        extra = {"sec_user_id": sec, "max_cursor": cursor, "count": "100" if cursor == "0" else "18",
                 "locate_query": "false", "show_live_replay_strategy": "1", "need_time_list": "1",
                 "time_list_query": "0", "whale_cut_token": "", "cut_version": "1", "publish_video_strategy_type": "2"}
        ref = f"https://www.douyin.com/user/{sec}"
        if cursor == "0":
            j = douyin_call("/aweme/v1/web/aweme/post/", extra, args, lambda j: isinstance(j.get("aweme_list"), list), referer=ref)
        else:
            # 实测（2026-11-03）：游客身份第 2 页起只回 {"status_code":0}；登录 cookie 才能继续翻页
            j = douyin_get("/aweme/v1/web/aweme/post/", extra, douyin_cookies(cookie_file=args.cookies), ref)
            if not isinstance(j.get("aweme_list"), list):
                oldest = min(((it["epoch"] or 0) for it in items if not it.get("is_top")), default=0)
                if args.since_epoch and oldest <= args.since_epoch:
                    break
                partial = (f"只拿到最新 {len(items)} 条（最早到 {ts(oldest)}），时间范围内可能还有更早的作品没扫到："
                           "抖音不让未登录的访客翻页。想扫全，先运行 login 让用户扫码登录，再重跑。")
                if not args.since_epoch:
                    partial = partial.replace("时间范围内", "")
                log(partial)
                break
        lst = j.get("aweme_list") or []
        for a in lst:
            if a["aweme_id"] in seen:
                continue
            seen.add(a["aweme_id"])
            if not author:
                au = a.get("author") or {}
                author = {"nickname": au.get("nickname"), "id": au.get("unique_id") or au.get("short_id"),
                          "home": f"https://www.douyin.com/user/{sec}"}
            items.append(douyin_item(a))
        log(f"已取 {len(items)} 条作品")
        if not j.get("has_more") or not lst:
            break
        if args.since_epoch and min(((a.get("create_time") or 0) for a in lst if not a.get("is_top")), default=1 << 40) < args.since_epoch:
            break  # 已翻到时间范围之前，不用再翻
        cursor = str(j.get("max_cursor"))
        time.sleep(random.uniform(1.5, 3.0))
    if not items:
        raise Blocked("主页没返回作品（账号私密/无作品/风控）。")
    return author, items, partial


def douyin_refresh_media(item, args):
    j = douyin_call("/aweme/v1/web/aweme/detail/", {"aweme_id": item["id"]}, args, lambda j: j.get("aweme_detail"))
    return douyin_item(j["aweme_detail"])["media_urls"]


# ============================================================ B站（游客 + WBI 签名）
_BILI = {}
def bili_client():
    if "c" in _BILI:
        return _BILI["c"], _BILI["mix"]
    import hashlib
    c = httpx_client(headers={"User-Agent": PC_UA, "Referer": "https://www.bilibili.com/"})
    spi = c.get("https://api.bilibili.com/x/frontend/finger/spi").json()["data"]
    c.cookies.set("buvid3", spi["b_3"], domain=".bilibili.com"); c.cookies.set("buvid4", spi["b_4"], domain=".bilibili.com")
    w = c.get("https://api.bilibili.com/x/web-interface/nav").json()["data"]["wbi_img"]
    raw = w["img_url"].rsplit("/", 1)[1].split(".")[0] + w["sub_url"].rsplit("/", 1)[1].split(".")[0]
    order = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
             37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]
    _BILI.update(c=c, mix="".join(raw[i] for i in order)[:32], md5=hashlib.md5)
    return _BILI["c"], _BILI["mix"]


def bili_get(path, params):
    c, mix = bili_client()
    p = dict(params, wts=int(time.time()))
    clean = lambda v: "".join(ch for ch in str(v) if ch not in "!'()*")
    q = "&".join(urllib.parse.quote(str(k), safe="") + "=" + urllib.parse.quote(clean(v), safe="") for k, v in sorted(p.items()))
    q += "&w_rid=" + _BILI["md5"]((q + mix).encode()).hexdigest()
    for i in range(3):
        r = c.get("https://api.bilibili.com" + path + "?" + q)
        try:
            j = r.json()
        except Exception:
            j = {"code": r.status_code, "message": r.text[:100]}
        if j.get("code") == 0:
            return j["data"]
        log(f"B站接口 {path}: {j.get('code')} {j.get('message')}，重试")
        time.sleep(3 + i * 3)
    raise Blocked(f"B站拒绝（{str(j.get('code'))[:10]} {str(j.get('message'))[:40]}）：多半是 B站临时风控（-352/412），等几分钟再试；别连续狂跑。")


def bili_list(url, args):
    if "b23.tv" in url:
        url = str(bili_client()[0].get(url).url)
    m = re.search(r"space\.bilibili\.com/(\d+)", url)
    if not m:
        bv = re.search(r"(BV[0-9A-Za-z]{10})", url)
        if not bv:
            raise ValueError(f"认不出 B站主页或视频：{url}")
        mid = str(bili_get("/x/web-interface/wbi/view", {"bvid": bv.group(1)})["owner"]["mid"])
    else:
        mid = m.group(1)
    # B站接口能直接按播放量(click)排序；按点赞时先取播放前 max_items 条再补点赞
    order = "pubdate" if args.since_epoch else "click"  # 有时间范围就按发布时间翻页、本地再排序
    items, pn, author = [], 1, {}
    dm = {"platform": "web", "web_location": "1550101", "dm_img_list": "[]",
          "dm_img_str": "V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ",
          "dm_cover_img_str": "QU5HTEUgKEludGVsLCBJbnRlbChSKSBVSEQgR3JhcGhpY3MgNjMwICgweDAwMDAzRTlCKSBEaXJlY3QzRDExIHZzXzVfMCBwc181XzAsIEQzRDExKUdvb2dsZSBJbmMuIChJbnRlbC",
          "dm_img_inter": '{"ds":[],"wh":[0,0,0],"of":[0,0,0]}'}
    cap = args.max_items if args.since_epoch else (min(args.max_items, max(args.top * 3, 30)) if args.sort == "likes" else args.top)
    while len(items) < cap:
        d = bili_get("/x/space/wbi/arc/search", {"mid": mid, "ps": 30, "pn": pn, "order": order, **dm})
        vl = d["list"]["vlist"]
        for v in vl:
            if str(v.get("mid")) == mid and not author:  # 合作视频的 author 可能是别人，只认 mid 一致的
                author = {"nickname": v.get("author"), "id": mid, "home": f"https://space.bilibili.com/{mid}"}
            items.append({"platform": "bilibili", "id": v["bvid"], "url": f"https://www.bilibili.com/video/{v['bvid']}",
                          "title": v.get("title"), "desc": v.get("description"), "publish_time": ts(v.get("created")), "epoch": v.get("created"),
                          "duration_str": v.get("length"), "plays": v.get("play"), "comments": v.get("comment"),
                          "likes": None, "type": "视频", "media_urls": []})
        log(f"已取 {len(items)} 条（共 {d['page']['count']}）")
        if not vl or pn * 30 >= d["page"]["count"]:
            break
        if args.since_epoch and min(v.get("created") or 0 for v in vl) < args.since_epoch:
            break
        pn += 1; time.sleep(random.uniform(1.5, 3))
    author = author or {"nickname": f"UP{mid}", "id": mid, "home": f"https://space.bilibili.com/{mid}"}
    if args.since_epoch:
        items = [i for i in items if (i.get("epoch") or 0) >= args.since_epoch]
    if args.sort != "plays":
        pool = sorted(items, key=lambda x: x.get("plays") or 0, reverse=True)[:max(args.top * 3, 30)]
        for it in pool:
            st = bili_get("/x/web-interface/wbi/view", {"bvid": it["id"]})["stat"]
            it.update(likes=st.get("like"), collects=st.get("favorite"), shares=st.get("share"), coins=st.get("coin"))
            time.sleep(random.uniform(0.8, 1.5))
        items = pool
        log(f"注意：按{args.sort}排序只在播放量前 {len(pool)} 条里比较")
    return author, items, None


def bili_download(item, dest):
    v = bili_get("/x/web-interface/wbi/view", {"bvid": item["id"]})
    pu = bili_get("/x/player/wbi/playurl", {"bvid": item["id"], "cid": v["cid"], "qn": 16, "fnval": 1, "platform": "html5"})
    for u in [pu["durl"][0]["url"]] + (pu["durl"][0].get("backup_url") or []):
        try:
            return http_download(u, dest, referer="https://www.bilibili.com/")
        except Exception as e:
            log("B站下载失败换备用：", e)
    raise RuntimeError("B站视频下载失败")


# ============================================================ YouTube 等（yt-dlp）
def ytdlp_bin():
    exe = shutil.which("yt-dlp")
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


def ytdlp_list(url, args):
    out = subprocess.run(ytdlp_bin() + ["--flat-playlist", "-J", "--no-warnings", "--extractor-args", "youtubetab:approximate_date", "-I", f"1:{args.max_items}", url],
                         capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        raise Blocked("yt-dlp 失败：" + out.stderr.strip()[-300:])
    j = json.loads(out.stdout)
    items = [{"platform": "youtube", "id": e.get("id"), "url": e.get("url") or e.get("webpage_url"),
              "title": e.get("title"), "desc": e.get("description"), "publish_time": ts(e.get("timestamp")), "epoch": e.get("timestamp"),
              "duration_sec": e.get("duration"), "plays": e.get("view_count"), "likes": None, "type": "视频", "media_urls": []}
             for e in j.get("entries") or [] if e.get("id")]
    if args.sort == "likes":
        log("YouTube 列表只有播放量，没有点赞数，改为按播放量排序")
        args.sort = "plays"
    return {"nickname": j.get("channel") or j.get("uploader") or j.get("title"), "id": j.get("channel_id"), "home": url}, items, None


# ============================================================ 下载 + 转写
def http_download(u, dest, referer=None):
    import httpx
    with httpx.stream("GET", u, headers={"User-Agent": PC_UA, **({"Referer": referer} if referer else {})},
                      follow_redirects=True, timeout=180) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for ch in r.iter_bytes(1 << 16):
                f.write(ch)
    if Path(dest).stat().st_size < 10000:
        raise RuntimeError("下载到的文件太小")
    return dest


def ffmpeg_bin():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        raise SystemExit("缺少 ffmpeg：pip install imageio-ffmpeg（自带 ffmpeg，Windows/Mac 都行）")


def to_wav(media, wav):
    subprocess.run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)


SV = "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09"
PUNCT = "sherpa-onnx-punct-ct-transformer-zh-en-vocab272727-2024-04-12-int8"
GH = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
GH_PUNCT = "https://github.com/k2-fsa/sherpa-onnx/releases/download/punctuation-models/"


def sensevoice_models():
    md = Path(os.environ.get("PLATFORM_SCRAPER_MODELS", HOME / "models"))
    for cand in (md, Path("/workspace/omni-scraper/models")):
        if (cand / SV / "model.int8.onnx").exists() and (cand / "silero_vad.onnx").exists() and (cand / PUNCT).exists():
            return cand
    md.mkdir(parents=True, exist_ok=True)
    pre = os.environ.get("GITHUB_PROXY", "")  # 国内下载慢时可设，如 https://<镜像>/ ；不设就直连 GitHub
    log("首次使用：下载 SenseVoice 语音识别模型（约 160MB，只下一次）…")
    if not (md / "silero_vad.onnx").exists():
        http_download(pre + GH + "silero_vad.onnx", md / "silero_vad.onnx")
    import tarfile
    for name, base in ((SV, GH), (PUNCT, GH_PUNCT)):
        if (md / name).exists():
            continue
        tb = md / (name + ".tar.bz2")
        http_download(pre + base + name + ".tar.bz2", tb)
        with tarfile.open(tb) as t:
            t.extractall(md)
        tb.unlink()
    return md


def asr_sensevoice(wav):
    import numpy as np, sherpa_onnx, wave
    md = sensevoice_models()
    rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(model=str(md / SV / "model.int8.onnx"), tokens=str(md / SV / "tokens.txt"),
                                                         num_threads=os.cpu_count() or 4, use_itn=True, language="auto")
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(md / "silero_vad.onnx")
    cfg.silero_vad.min_silence_duration = 0.3
    cfg.silero_vad.max_speech_duration = 20
    cfg.sample_rate = 16000
    vad = sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=3600)
    w = wave.open(str(wav))
    a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    segs = []
    def drain():
        while not vad.empty():
            segs.append(np.array(vad.front.samples)); vad.pop()
    ws = cfg.silero_vad.window_size
    for i in range(0, len(a), ws):
        vad.accept_waveform(a[i:i + ws]); drain()
    vad.flush(); drain()
    out = []
    for s in segs:
        for k in range(0, len(s), 25 * 16000):  # 兜底切成 <=25 秒
            st = rec.create_stream(); st.accept_waveform(16000, s[k:k + 25 * 16000]); rec.decode_stream(st)
            t = re.sub(r"<\|[^|]*\|>", "", st.result.text).strip()
            if t:
                out.append(t)
    # 整篇加标点（CT-Transformer），只加标点不改字，再按句切开
    raw = re.sub(r"[，。？！、；：,.?!;:]", " ", " ".join(out))
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return []
    pc = sherpa_onnx.OfflinePunctuation(sherpa_onnx.OfflinePunctuationConfig(
        model=sherpa_onnx.OfflinePunctuationModelConfig(ct_transformer=str(md / PUNCT / "model.int8.onnx"), num_threads=4)))
    txt = pc.add_punctuation(raw)
    txt = re.sub(r"(?<=[\u4e00-\u9fff，。？！、]) (?=[\u4e00-\u9fff])|(?<=[\u4e00-\u9fff]) (?=[，。？！、])", "", txt)
    return [x for x in re.findall(r"[^。？！]+[。？！]?", txt) if x.strip()]


def asr_whisper(wav, model):
    from faster_whisper import WhisperModel
    m = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(str(wav), language="zh", vad_filter=True, initial_prompt="以下是普通话的句子，使用简体中文和标点符号。")
    return [s.text.strip() for s in segs]


def pick_asr(name):
    if name in ("auto", "sensevoice"):
        try:
            import sherpa_onnx  # noqa
            return "sensevoice"
        except ImportError:
            if name == "sensevoice":
                raise SystemExit("缺少 sherpa-onnx：pip install sherpa-onnx numpy")
    try:
        import faster_whisper  # noqa
        return "whisper"
    except ImportError:
        raise SystemExit("没有可用的语音识别：pip install sherpa-onnx numpy（推荐）或 pip install faster-whisper")


def paragraphs(sents, n=200):
    paras, cur = [], ""
    for s in sents:
        if s and not re.search(r"[。！？!?.，,]$", s):
            s += "。"
        cur += s
        if len(cur) >= n and re.search(r"[。！？!?]$", cur):
            paras.append(cur); cur = ""
    return paras + ([cur] if cur else [])


def ytdlp_subs(url, tmp):
    subprocess.run(ytdlp_bin() + ["--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "zh-Hans,zh-CN,zh.*,en",
                                  "--convert-subs", "srt", "-o", str(tmp / "s.%(ext)s"), "--no-warnings", url],
                   capture_output=True, text=True, timeout=300)
    for f in sorted(tmp.glob("s.*.srt")):
        lines = [l.strip() for l in f.read_text(encoding="utf-8", errors="ignore").splitlines()
                 if l.strip() and not l.strip().isdigit() and "-->" not in l]
        dedup = [l for i, l in enumerate(lines) if i == 0 or l != lines[i - 1]]
        if dedup:
            return dedup, f"平台字幕:{f.name}"
    return None, None


def transcribe_item(item, tmp, args, engine):
    tmp.mkdir(parents=True, exist_ok=True)
    if item["platform"] not in ("douyin", "bilibili", "local"):
        s, src = ytdlp_subs(item["url"], tmp)
        if s:
            return s, src
        subprocess.run(ytdlp_bin() + ["-f", "ba/b", "-o", str(tmp / "media.%(ext)s"), "--no-warnings", item["url"]], check=True, timeout=1800)
        media = next(p for p in tmp.iterdir() if p.stem == "media")
    elif item["platform"] == "bilibili":
        media = bili_download(item, tmp / "media.mp4")
    elif item["platform"] == "douyin":
        if item.get("type") == "图文":
            return None, "图文作品，无语音"
        media = None
        for urls in (item.get("media_urls") or [], None):
            if urls is None:
                log("播放地址过期，重新取一次"); urls = douyin_refresh_media(item, args)
            for u in urls:
                try:
                    media = http_download(u, tmp / "media.mp4", referer="https://www.douyin.com/"); break
                except Exception as e:
                    log("下载失败换 CDN：", e)
            if media:
                break
        if not media:
            raise RuntimeError("抖音视频下载失败")
    else:
        media = Path(item["url"])
    wav = tmp / "a16k.wav"
    to_wav(media, wav)
    t0 = time.time()
    sents = asr_sensevoice(wav) if engine == "sensevoice" else asr_whisper(wav, args.whisper_model)
    log(f"转写 {time.time() - t0:.0f}s")
    return sents, f"本地语音识别:{engine}"


def stat_line(it):
    names = [("plays", "播放"), ("likes", "点赞"), ("comments", "评论"), ("collects", "收藏"), ("shares", "转发"), ("coins", "投币")]
    return "，".join(f"{cn} {it[k]:,}" for k, cn in names if isinstance(it.get(k), int))


def write_item_md(path, it, author, paras, source, comments=None):
    md = [f"# {it.get('title') or ''}", "",
          f"- 平台：{PLAT_CN.get(it['platform'], it['platform'])}　作者：{author.get('nickname')}",
          f"- 链接：{it.get('url')}", f"- 发布：{it.get('publish_time') or '未知'} (UTC+8)　时长：{it.get('duration_sec') or it.get('duration_str') or '?'} 秒",
          f"- 数据：{stat_line(it)}（抓取于 {datetime.datetime.now(TZ8):%Y-%m-%d %H:%M} UTC+8）",
          f"- 文字来源：{source}（机器识别，专有名词可能有错）", "",
          "## 简介", "", it.get("desc") or "", "", "## 逐字稿", ""] + [p + "\n" for p in paras]
    if comments:
        md += ["## 热门评论（按点赞）", ""] + [f"- {c['likes']}赞｜{c['user']}：{c['text']}" for c in comments] + [""]
    elif comments is not None:
        md += ["## 热门评论", "", "（没取到评论：平台未返回或需要登录）", ""]
    path.write_text("\n".join(md), encoding="utf-8")


# ============================================================ 命令
def detect(url):
    host = urllib.parse.urlsplit(url).netloc.lower()
    if re.search(r"douyin\.com|iesdouyin\.com", host): return "douyin"
    if re.search(r"bilibili\.com|b23\.tv", host): return "bilibili"
    if re.search(r"youtube\.com|youtu\.be", host): return "youtube"
    if re.search(r"xiaohongshu\.com|xhslink\.com|rednote", host): return "xiaohongshu"
    if re.search(r"weixin\.qq\.com|channels", host): return "weixin_channels"
    return "other"


def parse_since(v):
    """'180d' '6m' '3m' '1y' '2026-05-01' 'all' -> epoch 秒（None=不限）。"""
    v = (v or "all").strip().lower()
    if v in ("all", "0", "none", "不限"):
        return None
    m = re.fullmatch(r"(\d+)\s*([dwmy])", v)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return int(time.time() - n * {"d": 1, "w": 7, "m": 30, "y": 365}[u] * 86400)
    return int(datetime.datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=TZ8).timestamp())


def is_single(url, plat):
    if plat == "douyin":
        if re.search(r"/user/", url) and not re.search(r"modal_id=", url):
            return False
        if re.search(r"v\.douyin\.com|iesdouyin\.com", url):
            with httpx_client() as c:
                final = str(c.get(url, headers={"User-Agent": MOB_UA}).url)
            return not re.search(r"/user/", final)
        return True
    if plat == "bilibili":
        return not re.search(r"space\.bilibili\.com", url)
    if plat == "youtube":
        return bool(re.search(r"watch\?|youtu\.be/|/shorts/", url))
    return True


def fetch_comments(it, args):
    n = args.with_comments
    out = []
    try:
        if it["platform"] == "douyin":
            cursor = 0
            while len(out) < n:
                j = douyin_get("/aweme/v1/web/comment/list/", {"aweme_id": it["id"], "cursor": str(cursor), "count": "20", "item_type": "0"},
                               douyin_cookies(cookie_file=args.cookies), f"https://www.douyin.com/video/{it['id']}")
                cs = j.get("comments") or []
                out += [{"likes": c.get("digg_count") or 0, "user": (c.get("user") or {}).get("nickname"), "text": (c.get("text") or "").replace("\n", " ")} for c in cs]
                if not j.get("has_more") or not cs:
                    break
                cursor = j.get("cursor"); time.sleep(random.uniform(1, 2))
        elif it["platform"] == "bilibili":
            v = bili_get("/x/web-interface/wbi/view", {"bvid": it["id"]})
            d = bili_get("/x/v2/reply/wbi/main", {"oid": v["aid"], "type": 1, "mode": 3, "pagination_str": '{"offset":""}'})
            out = [{"likes": r.get("like") or 0, "user": r["member"]["uname"], "text": r["content"]["message"].replace("\n", " ")}
                   for r in (d.get("replies") or [])]
    except Exception as e:
        log("评论没取到：", str(e)[:120])
    return sorted(out, key=lambda c: c["likes"], reverse=True)[:n]


def fetch_single(url, args):
    plat = detect(url)
    if plat == "douyin":
        final = str(httpx_client().get(url, headers={"User-Agent": MOB_UA}).url) if re.search(r"v\.douyin\.com", url) else url
        vm = re.search(r"/(?:video|note|slides)/(\d+)", final) or re.search(r"modal_id=(\d+)", final)
        if not vm:
            raise ValueError(f"认不出抖音作品：{final}")
        d = douyin_call("/aweme/v1/web/aweme/detail/", {"aweme_id": vm.group(1)}, args, lambda j: j.get("aweme_detail"))["aweme_detail"]
        au = d.get("author") or {}
        return {"nickname": au.get("nickname"), "home": f"https://www.douyin.com/user/{au.get('sec_uid')}"}, douyin_item(d)
    if plat == "bilibili":
        if "b23.tv" in url:
            url = str(bili_client()[0].get(url).url)
        bv = re.search(r"(BV[0-9A-Za-z]{10})", url)
        if not bv:
            raise ValueError(f"认不出 B站视频：{url}")
        v = bili_get("/x/web-interface/wbi/view", {"bvid": bv.group(1)})
        st = v.get("stat") or {}
        return ({"nickname": v["owner"]["name"], "home": f"https://space.bilibili.com/{v['owner']['mid']}"},
                {"platform": "bilibili", "id": v["bvid"], "url": f"https://www.bilibili.com/video/{v['bvid']}", "title": v.get("title"),
                 "desc": v.get("desc"), "publish_time": ts(v.get("pubdate")), "epoch": v.get("pubdate"), "duration_sec": v.get("duration"),
                 "plays": st.get("view"), "likes": st.get("like"), "comments": st.get("reply"), "collects": st.get("favorite"),
                 "shares": st.get("share"), "coins": st.get("coin"), "type": "视频"})
    out = subprocess.run(ytdlp_bin() + ["-J", "--no-playlist", "--no-warnings"] + (["--cookies", args.cookies] if args.cookies else []) + [url],
                         capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise Blocked(f"{plat} 单条解析失败（yt-dlp）：" + out.stderr.strip()[-300:])
    j = json.loads(out.stdout)
    return ({"nickname": j.get("uploader") or j.get("channel"), "home": j.get("uploader_url") or j.get("channel_url")},
            {"platform": plat, "id": j.get("id"), "url": j.get("webpage_url") or url, "title": j.get("title"), "desc": j.get("description"),
             "publish_time": ts(j.get("timestamp")), "epoch": j.get("timestamp"), "duration_sec": j.get("duration"),
             "plays": j.get("view_count"), "likes": j.get("like_count"), "comments": j.get("comment_count"), "type": "视频"})


def cmd_single(url, args):
    author, it = fetch_single(url, args)
    plat = it["platform"]
    folder = Path(args.out).expanduser() / f"{PLAT_CN.get(plat, plat)}_{safe_name(author.get('nickname'), 30)}"
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{safe_name(it.get('title'))}.md"
    tmp = folder / ".tmp" / str(it["id"])
    try:
        sents, src = (None, "未转写（--no-transcript）") if args.no_transcript else transcribe_item(it, tmp, args, pick_asr(args.asr))
    finally:
        shutil.rmtree(folder / ".tmp", ignore_errors=True) if not args.keep_media else None
    comments = fetch_comments(it, args) if args.with_comments else None
    write_item_md(out, it, author, paragraphs(sents) if sents else ["（无语音内容或未转写）"], src, comments)
    return {"ok": True, "mode": "single", "file": str(out), "title": it.get("title"), "author": author.get("nickname"),
            "stats": {k: it.get(k) for k in ("plays", "likes", "comments", "collects", "shares")}, "source": src,
            "chars": sum(len(x) for x in sents or []), "comments_saved": len(comments or [])}


def cmd_list(args):
    url = extract_url(args.input)
    if not url:
        done({"ok": False, "error": "输入里没有链接"}, 4)
    plat = detect(url)
    if plat not in ("douyin", "bilibili", "youtube"):
        done({"ok": False, "platform": plat, "error": f"本脚本暂不支持 {plat} 主页列表，按 SKILL.md 的备选方案处理"}, 4)
    author, items, partial = {"douyin": douyin_list, "bilibili": bili_list, "youtube": ytdlp_list}[plat](url, args)
    if args.since_epoch:
        nodate = [i for i in items if not i.get("epoch")]
        items = [i for i in items if (i.get("epoch") or 0) >= args.since_epoch]
        if nodate:
            log(f"{len(nodate)} 条没有发布时间，已排除")
    key = args.sort
    ranked = sorted(items, key=lambda x: (x.get(key) or 0), reverse=True)
    top = ranked[:args.top]
    folder = Path(args.out).expanduser() / f"{PLAT_CN[plat]}_{safe_name(author.get('nickname'), 30)}"
    folder.mkdir(parents=True, exist_ok=True)
    for i, it in enumerate(top, 1):
        it["rank"] = i
    data = {"platform": plat, "author": author, "sort": key, "since": args.since, "matched": len(items), "coverage_note": partial, "fetched_at": datetime.datetime.now(TZ8).isoformat(timespec="seconds"),
            "top": top}
    (folder / "works.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    cn = {"likes": "点赞", "plays": "播放", "comments": "评论", "collects": "收藏", "shares": "转发"}[key]
    rng = "全部作品" if not args.since_epoch else f"{ts(args.since_epoch)[:10]} 之后发布"
    lines = [f"# {author.get('nickname')} · {PLAT_CN[plat]} · {rng} · {cn}最高的 {len(top)} 条", "",
             f"- 主页：{author.get('home')}", f"- 时间范围内作品数：{len(items)}（按{cn}从高到低）",
             f"- 抓取时间：{datetime.datetime.now(TZ8):%Y-%m-%d %H:%M} (UTC+8)"] + ([f"- ⚠️ {partial}"] if partial else []) + ["",
             "| # | 标题 | 发布 | " + "播放 | 点赞 | 评论 | 收藏 | 转发 | 链接 |", "|---|---|---|---|---|---|---|---|---|"]
    f = lambda v: f"{v:,}" if isinstance(v, int) else "-"
    for it in top:
        t = safe_name(it.get("title"), 36) + ("（置顶）" if it.get("is_top") else "") + ("（图文）" if it.get("type") == "图文" else "")
        lines.append(f"| {it['rank']} | {t} | {(it.get('publish_time') or '')[:10]} | {f(it.get('plays'))} | {f(it.get('likes'))} | "
                     f"{f(it.get('comments'))} | {f(it.get('collects'))} | {f(it.get('shares'))} | [打开]({it['url']}) |")
    if plat == "douyin":
        lines += ["", "> 抖音不公开别人作品的播放量（接口返回 0），所以按点赞排序。"]
    (folder / "00_作品清单.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log("清单：", folder / "00_作品清单.md")
    return folder, data


def cmd_transcribe(works_json, args):
    data = json.loads(Path(works_json).read_text(encoding="utf-8"))
    folder = Path(works_json).parent
    engine = None if args.no_transcript else pick_asr(args.asr)
    res = []
    for it in data["top"][:args.top]:
        name = f"{it['rank']:02d}_{safe_name(it.get('title'))}.md"
        out = folder / name
        if out.exists() and not args.force:
            res.append({"rank": it["rank"], "file": str(out), "status": "已存在，跳过"}); continue
        tmp = folder / ".tmp" / str(it["id"])
        try:
            log(f"[{it['rank']}/{len(data['top'])}] {it.get('title')}")
            sents, src = (None, "未转写（--no-transcript）") if args.no_transcript else transcribe_item(it, tmp, args, engine)
            comments = fetch_comments(it, args) if args.with_comments else None
            write_item_md(out, it, data["author"], paragraphs(sents) if sents else ["（无语音内容）"], src, comments)
            res.append({"rank": it["rank"], "file": str(out), "status": "ok", "source": src,
                        "chars": sum(len(s) for s in sents or [])})
        except Blocked as e:
            res.append({"rank": it["rank"], "status": "blocked", "error": str(e)}); break
        except Exception as e:
            res.append({"rank": it["rank"], "status": "failed", "error": str(e)[:200]})
        finally:
            if not args.keep_media:
                shutil.rmtree(tmp, ignore_errors=True)
        time.sleep(random.uniform(1, 2))
    shutil.rmtree(folder / ".tmp", ignore_errors=True) if not args.keep_media else None
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "list", "video", "transcribe", "file", "doctor", "login"):
        p = sub.add_parser(name)
        if name not in ("doctor", "login"):
            p.add_argument("input")
        p.add_argument("--out", "--kb", dest="out", default=str(Path.home() / "知识库" / "对标博主"), help="知识库目录")
        p.add_argument("--top", type=int, default=10)
        p.add_argument("--since", default="180d", help="时间范围：180d / 3m / 1y / 2026-05-01 / all（默认近半年）")
        p.add_argument("--with-comments", type=int, nargs="?", const=30, default=0, help="附带热门评论，默认 30 条")
        p.add_argument("--no-transcript", action="store_true", help="只要数据不转写")
        p.add_argument("--author", action="store_true", help="给的是视频链接但要调研它的作者主页")
        p.add_argument("--sort", default="likes", choices=["likes", "plays", "comments", "collects", "shares"])
        p.add_argument("--max-items", type=int, default=300, help="最多扫描多少条作品再排序")
        p.add_argument("--cookies", help="可选：登录后的 cookie 文件（'k=v; k2=v2' 或 JSON）")
        p.add_argument("--asr", default="auto", choices=["auto", "sensevoice", "whisper"])
        p.add_argument("--whisper-model", default="small")
        p.add_argument("--keep-media", action="store_true")
        p.add_argument("--force", action="store_true")
    args = ap.parse_args()
    args.since_epoch = parse_since(args.since) if hasattr(args, "since") else None
    try:
        if args.cmd == "doctor":
            r = {}
            for mod in ("httpx", "playwright", "sherpa_onnx", "numpy", "faster_whisper", "imageio_ffmpeg", "yt_dlp"):
                try:
                    __import__(mod); r[mod] = True
                except ImportError:
                    r[mod] = False
            r["ffmpeg_in_path"] = bool(shutil.which("ffmpeg"))
            r["models_ready"] = any((c / SV / "model.int8.onnx").exists() for c in (HOME / "models", Path("/workspace/omni-scraper/models")))
            need = [m for m in ("httpx", "playwright") if not r[m]]
            if not (r["sherpa_onnx"] or r["faster_whisper"]): need.append("sherpa-onnx numpy")
            if not (r["ffmpeg_in_path"] or r["imageio_ffmpeg"]): need.append("imageio-ffmpeg")
            done({"ok": not need, "deps": r, "pip_install": " ".join(need) or None}, 0 if not need else 2)
        if args.cmd == "login":
            ok = douyin_login()
            done({"ok": ok, "message": "已保存抖音登录态" if ok else "超时未登录，可重试"}, 0 if ok else 3)
        if args.cmd == "file":
            engine = pick_asr(args.asr)
            p = Path(args.input).expanduser()
            it = {"platform": "local", "id": p.stem, "url": str(p), "title": p.stem, "rank": 0}
            sents, src = transcribe_item(it, Path(args.out).expanduser() / ".tmp" / "local", args, engine)
            out = Path(args.out).expanduser() / f"{safe_name(p.stem)}.md"
            write_item_md(out, it, {"nickname": "本地文件"}, paragraphs(sents), src)
            shutil.rmtree(Path(args.out).expanduser() / ".tmp", ignore_errors=True)
            done({"ok": True, "file": str(out)})
        if args.cmd == "transcribe":
            res = cmd_transcribe(args.input, args)
            done({"ok": all(r["status"] != "failed" for r in res) and not any(r["status"] == "blocked" for r in res), "results": res},
                 3 if any(r["status"] == "blocked" for r in res) else 0)
        if args.cmd in ("run", "video"):
            url = extract_url(args.input)
            if not url:
                done({"ok": False, "error": "输入里没有链接"}, 4)
            if args.cmd == "video" or (not args.author and is_single(url, detect(url))):
                done(cmd_single(url, args))
        folder, data = cmd_list(args)
        summary = [{"rank": t["rank"], "title": t.get("title"), "likes": t.get("likes"), "plays": t.get("plays"), "url": t["url"]} for t in data["top"]]
        if args.cmd == "list":
            done({"ok": True, "folder": str(folder), "list_md": str(folder / "00_作品清单.md"), "works_json": str(folder / "works.json"),
                  "matched": data["matched"], "coverage_note": data.get("coverage_note"), "top": summary})
        res = cmd_transcribe(folder / "works.json", args)
        done({"ok": True, "folder": str(folder), "matched": data["matched"], "top": summary, "transcripts": res},
             3 if any(r["status"] == "blocked" for r in res) else 0)
    except Blocked as e:
        done({"ok": False, "blocked": True, "error": str(e)}, 3)
    except ValueError as e:
        done({"ok": False, "error": str(e)}, 4)


if __name__ == "__main__":
    main()
