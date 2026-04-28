const axios = require("axios");
const crypto = require("crypto");

/**
 * =========================
 * 代理池（自动失败切换）
 * =========================
 */
const PROXIES = [
  "https://proxy.showlo.gv.uy/?url=",
  "https://proxy2.showlo.gv.uy/?url="
];

function proxyUrl(url, index = 0) {
  return PROXIES[index] + encodeURIComponent(url);
}

/**
 * =========================
 * 基础配置
 * =========================
 */
const SECRET = "0fOiukQq7jXZV2GRi9LGlO";
const API_HOST = "api.pingmeapp.net";

const MAX_VIDEO = 5;
const VIDEO_DELAY = 8000;
const ACCOUNT_GAP = 3500;

const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN || "";
const TG_USER_ID = process.env.TG_USER_ID || "";

/**
 * =========================
 * 工具
 * =========================
 */
function md5(str) {
  return crypto.createHash("md5").update(str).digest("hex");
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function getUTCSignDate() {
  const now = new Date();
  const pad = n => String(n).padStart(2, "0");

  return `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())}`;
}

/**
 * =========================
 * 风控识别（关键）
 * =========================
 */
function isBlocked(data) {
  if (!data) return true;

  const msg = (data.retmsg || "").toLowerCase();

  return (
    msg.includes("验证码") ||
    msg.includes("图形") ||
    msg.includes("captcha") ||
    msg.includes("verify") ||
    msg.includes("challenge")
  );
}

/**
 * =========================
 * 签名
 * =========================
 */
function buildSignedParamsRaw(account) {
  const params = {};

  Object.keys(account.paramsRaw || {}).forEach(k => {
    if (k !== "sign" && k !== "signDate") {
      params[k] = account.paramsRaw[k];
    }
  });

  params.signDate = getUTCSignDate();

  const signBase = Object.keys(params)
    .sort()
    .map(k => `${k}=${params[k]}`)
    .join("&");

  params.sign = md5(signBase + SECRET);

  return params;
}

function buildUrl(path, account) {
  const params = buildSignedParamsRaw(account);

  const qs = Object.keys(params)
    .map(k => `${k}=${encodeURIComponent(params[k])}`)
    .join("&");

  return `https://${API_HOST}/app/${path}?${qs}`;
}

/**
 * =========================
 * headers
 * =========================
 */
function buildHeaders(account) {
  return {
    Host: API_HOST,
    Accept: "application/json",
    "Accept-Language": "zh-Hans-CN;q=1.0",
    "Accept-Encoding": "gzip, deflate, br",
    "User-Agent": account.headers?.["User-Agent"] || "PingMe/1.9.3"
  };
}

/**
 * =========================
 * 请求（双代理）
 * =========================
 */
async function fetchApi(path, account) {
  const rawUrl = buildUrl(path, account);
  const headers = buildHeaders(account);

  let lastErr = null;

  for (let i = 0; i < PROXIES.length; i++) {
    const url = proxyUrl(rawUrl, i);

    try {
      const resp = await axios.get(url, {
        headers,
        timeout: 20000
      });

      return resp.data;
    } catch (e) {
      lastErr = {
        retcode: -1,
        retmsg: e.message
      };
    }

    console.log(`⚠️ Proxy${i + 1} failed → switching`);
  }

  return lastErr || { retcode: -1, retmsg: "all proxy failed" };
}

/**
 * =========================
 * TG通知
 * =========================
 */
async function sendTG(title, content) {
  if (!TG_BOT_TOKEN || !TG_USER_ID) return;

  try {
    await axios.post(`https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`, {
      chat_id: TG_USER_ID,
      text: `${title}\n\n${content}`,
      parse_mode: "HTML"
    });
  } catch (e) {
    console.log("TG失败:", e.message);
  }
}

/**
 * =========================
 * 单账号执行
 * =========================
 */
async function runAccount(account, index, total) {
  const tag = `[账号${index + 1}/${total}]`;
  const msgs = [tag];

  console.log(`\n===== ${tag} START =====\n`);

  let data = await fetchApi("queryBalanceAndBonus", account);
  msgs.push(`💰 当前余额：${data?.result?.balance || 0}`);

  data = await fetchApi("checkIn", account);
  msgs.push(`签到：${data?.retmsg || "OK"}`);

  /**
   * 视频奖励（重点：风控识别）
   */
  for (let i = 1; i <= MAX_VIDEO; i++) {
    await sleep(VIDEO_DELAY);

    data = await fetchApi("videoBonus", account);

    // ❌ 风控直接停止
    if (isBlocked(data)) {
      msgs.push(`⛔ 视频${i}：触发验证码 / 风控，停止执行`);
      break;
    }

    if (data?.retcode !== 0) {
      msgs.push(`⏸ 视频${i}：${data?.retmsg || "失败"}`);
      break;
    }

    msgs.push(`🎬 视频${i}：+${data?.result?.bonus || 0}`);
  }

  data = await fetchApi("queryBalanceAndBonus", account);
  msgs.push(`💰 最新余额：${data?.result?.balance || 0}`);

  console.log(msgs.join("\n"));
  console.log(`\n===== ${tag} END =====\n`);

  return msgs.join("\n");
}

/**
 * =========================
 * 主函数
 * =========================
 */
async function main() {
  const accounts = [
    process.env.PINGME_DATA_1,
    process.env.PINGME_DATA_2,
    process.env.PINGME_DATA_3,
    process.env.PINGME_DATA_4,
    process.env.PINGME_DATA_5
  ]
    .filter(Boolean)
    .map(x => {
      try {
        return JSON.parse(x);
      } catch {
        return null;
      }
    })
    .filter(Boolean);

  if (!accounts.length) {
    console.log("❌ 无账号");
    return;
  }

  const results = [];

  for (let i = 0; i < accounts.length; i++) {
    const res = await runAccount(accounts[i], i, accounts.length);
    results.push(res);

    if (i < accounts.length - 1) {
      await sleep(ACCOUNT_GAP);
    }
  }

  const finalMsg = results.join("\n——————————\n");

  console.log("\n===== ALL DONE =====\n");
  console.log(finalMsg);

  await sendTG("PingMe 完成", finalMsg);
}

main();
