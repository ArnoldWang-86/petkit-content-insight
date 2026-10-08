// collect.js —— 宠物智能硬件内容采集（B站公开搜索接口）
// 支持分批采集 + 断点续采：随时中断，下次从没采完的关键词继续
//   PAGES=10 node src/collect.js     每个关键词翻多少页
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ROOT = path.join(__dirname, "..");
const RAW = path.join(ROOT, "data", "raw");
const OUT = path.join(RAW, "search_raw.jsonl");
const STATE = path.join(RAW, "_collect_state.json");
fs.mkdirSync(RAW, { recursive: true });

// B站 wbi 签名用的字符重排表（与 bili.py 中 MIXIN_TAB 完全一致）
const MIXIN_TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52];
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36";
const FIELDS = ["bvid","aid","title","description","pubdate","duration","play","like","favorites","danmaku","review","author","mid","tag","typename","typeid","arcurl"];

// 关键词三层结构：品类词量产品线热度 / 品牌词量声量份额 / 痛点场景词挖用户抱怨
const KEYWORDS = [
  "智能猫砂盆","自动猫砂盆","宠物饮水机","猫咪饮水机","自动喂食器","宠物喂食器",
  "宠物摄像头","宠物烘干箱","宠物烘干机","智能猫窝","宠物加热垫","自动铲屎机",
  "宠物智能","猫砂盆推荐","宠物自动厕所",
  "小佩宠物","PETKIT","霍曼宠物","CATLINK","catlink猫砂盆","小佩猫砂盆",
  "小米宠物","宠物智能品牌",
  "猫砂盆异味","猫咪不喝水","猫泌尿","猫毛满天飞","上班族养猫","出差喂猫",
  "猫砂盆怎么选","猫砂盆测评","宠物饮水机测评","养猫神器","养狗神器","宠物拆家",
];

const sleep = ms => new Promise(r => setTimeout(r, ms));
const md5 = s => crypto.createHash("md5").update(s).digest("hex");
let mixin = "";

async function boot() {
  const r = await fetch("https://api.bilibili.com/x/web-interface/nav", {
    headers: { "User-Agent": UA, Referer: "https://www.bilibili.com/" },
  });
  const j = await r.json();
  const w = j.data.wbi_img;
  const raw = w.img_url.split("/").pop().split(".")[0] + w.sub_url.split("/").pop().split(".")[0];
  mixin = MIXIN_TAB.map(i => raw[i]).join("").slice(0, 32);
}

async function search(kw, page, order) {
  for (let t = 0; t < 6; t++) {
    const p = { search_type: "video", keyword: kw, page: String(page), wts: String(Math.floor(Date.now() / 1000)) };
    if (order) p.order = order;
    const q = Object.keys(p).sort().map(k => encodeURIComponent(k) + "=" + encodeURIComponent(p[k])).join("&");
    p.w_rid = md5(q + mixin);
    const qs = Object.keys(p).map(k => encodeURIComponent(k) + "=" + encodeURIComponent(p[k])).join("&");
    try {
      const r = await fetch("https://api.bilibili.com/x/web-interface/search/type?" + qs, {
        headers: { "User-Agent": UA, Referer: "https://www.bilibili.com/", Accept: "application/json" },
      });
      const j = await r.json();
      if (j.code === 0) return j.data && j.data.result ? j.data.result : [];
      if (j.code === -412 || j.code === -352) { await sleep(3000 * (t + 1)); await boot(); continue; }
      return [];
    } catch (e) {
      await sleep(2500 * (t + 1));
    }
  }
  return null;  // null = 请求彻底失败，与「这一页确实没有结果」区分开
}

const strip = s => (typeof s === "string" ? s.replace(/<\/?em[^>]*>/g, "").replace(/&quot;/g, '"').trim() : s);

(async () => {
  await boot();

  let state = { done: [] };
  if (fs.existsSync(STATE)) { try { state = JSON.parse(fs.readFileSync(STATE, "utf8")); } catch (e) {} }
  const done = new Set(state.done || []);

  const seen = new Set();
  let existingRows = 0;
  if (fs.existsSync(OUT)) {
    for (const line of fs.readFileSync(OUT, "utf8").split("\n")) {
      if (!line.trim()) continue;
      existingRows++;
      try { const r = JSON.parse(line); if (r.bvid) seen.add(r.bvid); } catch (e) {}
    }
  }
  const uniqueBefore = seen.size;

  const PAGE_LIMIT = Number(process.env.PAGES || 10);
const ORDERS = ["", "", "click", "", "pubdate"];
  const out = fs.createWriteStream(OUT, { flags: "a" });
  let added = 0;

  const batch = KEYWORDS.filter(k => !done.has(k));

  if (!batch.length) {
    console.log("所有关键词都已采集完成，无需重复采集。");
    out.end();
    return;
  }

  for (let i = 0; i < batch.length; i++) {
    const kw = batch[i];
    const t0 = Date.now();
    let pagesOk = 0, rowsHere = 0;
    for (let pg = 1; pg <= PAGE_LIMIT; pg++) {
      const res = await search(kw, pg, ORDERS[(pg - 1) % ORDERS.length]);
      if (res === null) { console.log("      p" + pg + " 请求失败，跳过该页"); break; }
      if (!res.length) break;
      pagesOk++;
      for (const it of res) {
        if (!it.bvid) continue;
        const rec = { _keyword: kw, _page: pg, _ts: new Date().toISOString().slice(0, 19) };
        for (const f of FIELDS) rec[f] = (f === "title" || f === "description") ? strip(it[f]) : it[f];
        seen.add(it.bvid);
        out.write(JSON.stringify(rec) + "\n");
        added++; rowsHere++;
      }
      // 限速可配置：默认 900~1400ms；被 B站 风控（-412）时用 DELAY 调大，例如 DELAY=3000
      await sleep(Number(process.env.DELAY || 900) + Math.random() * 600);
    }
    done.add(kw);
    state.done = KEYWORDS.filter(k => done.has(k));
    fs.writeFileSync(STATE, JSON.stringify(state, null, 1));
    console.log("  [" + (i + 1) + "/" + batch.length + "] " + kw.padEnd(12, " ") +
      pagesOk + "页 / " + rowsHere + "行 / " + ((Date.now() - t0) / 1000).toFixed(0) + "s" +
      "   （累计唯一视频 " + seen.size + "）");
  }

  out.end();
  await new Promise(r => out.on("finish", r));

  console.log("");
  console.log("本次完成 " + batch.length + " 个关键词，新增 " + added + " 行");
  console.log("唯一视频 " + uniqueBefore + " -> " + seen.size);
  console.log("总进度 " + done.size + "/" + KEYWORDS.length + " 个关键词");

  if (done.size >= KEYWORDS.length) {
    console.log("");
    console.log("全部关键词采集完成！");
  } else {
    console.log("");
    console.log("还剩 " + (KEYWORDS.length - done.size) + " 个关键词，再跑一次本批文件继续。");
  }
})();
