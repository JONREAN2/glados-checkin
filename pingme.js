// 文件路径：pingme.js

/**
 * PingMe GitHub Actions 自动签到 + 视频奖励 + TG通知
 *
 * 保持原有 Secrets：
 * PINGME_DATA_1
 * PINGME_DATA_2
 * PINGME_DATA_3
 * PINGME_DATA_4
 * PINGME_DATA_5
 * TG_BOT_TOKEN
 * TG_USER_ID
 *
 * 兼容原账号格式和 QX capture 格式。
 */

const axios = require("axios");
const crypto = require("crypto");

const SECRET = "0fOiukQq7jXZV2GRi9LGlO";
const API_HOST = "api.pingmeapp.net";

const MAX_VIDEO = 5;
const VIDEO_DELAY = 8000;
const ACCOUNT_GAP = 3500;

const TG_BOT_TOKEN = process.env.TG_BOT_TOKEN || "";
const TG_USER_ID = process.env.TG_USER_ID || "";

const IOS_VERSIONS = [
  "17.5.1", "17.6.1", "17.4.1", "17.2.1", "16.7.8",
  "17.6", "17.3.1", "18.0.1", "17.1.2", "16.6.1"
];

const IOS_SCALES = ["2.00", "3.00", "3.00", "2.00", "3.00"];

const IPHONE_MODELS = [
  "iPhone14,3", "iPhone13,3", "iPhone15,3", "iPhone16,1",
  "iPhone14,7", "iPhone13,2", "iPhone15,2", "iPhone12,1"
];

const CFN_VERS = [
  "1410.0.3", "1494.0.7", "1568.100.1",
  "1209.1", "1474.0.4", "1568.200.2"
];

const DARWIN_VERS = [
  "22.6.0", "23.5.0", "23.6.0", "24.0.0", "22.4.0"
];

function md5(str) {
  return crypto.createHash("md5").update(str).digest("hex");
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function getUTCSignDate() {
  const now = new Date();
  const pad = n => String(n).padStart(2, "0");

  return `${now.getUTCFullYear()}-${pad(now.getUTCMonth() + 1)}-${pad(now.getUTCDate())} ${pad(now.getUTCHours())}:${pad(now.getUTCMinutes())}:${pad(now.getUTCSeconds())}`;
}

function pickItem(arr, seed) {
  return arr[seed % arr.length];
}

function buildUA(baseUA, seed) {
  const iosVer = pickItem(IOS_VERSIONS, seed);
  const scale = pickItem(IOS_SCALES, seed + 1);
  const model = pickItem(IPHONE_MODELS, seed + 2);
  const cfn = pickItem(CFN_VERS, seed + 3);
  const darwin = pickItem(DARWIN_VERS, seed + 4);

  if (baseUA && typeof baseUA === "string") {
    let ua = baseUA;
    let changed = false;

    if (/iOS \d+(\.\d+){0,2}/.test(ua)) {
      ua = ua.replace(/iOS \d+(\.\d+){0,2}/, `iOS ${iosVer}`);
      changed = true;
    }

    if (/Scale\/\d+(\.\d+)?/.test(ua)) {
      ua = ua.replace(/Scale\/\d+(\.\d+)?/, `Scale/${scale}`);
      changed = true;
    }

    if (/iPhone\d+,\d+/.test(ua)) {
      ua = ua.replace(/iPhone\d+,\d+/, model);
      changed = true;
    }

    if (/CFNetwork\/[\d.]+/.test(ua)) {
      ua = ua.replace(/CFNetwork\/[\d.]+/, `CFNetwork/${cfn}`);
      changed = true;
    }

    if (/Darwin\/[\d.]+/.test(ua)) {
      ua = ua.replace(/Darwin\/[\d.]+/, `Darwin/${darwin}`);
      changed = true;
    }

    if (changed) return ua;
  }

  return `PingMe/1.0.0 (${model}; iOS ${iosVer}; Scale/${scale}) CFNetwork/${cfn} Darwin/${darwin}`;
}

function buildSignedParamsRaw(capture, overrideDeviceId) {
  const params = {};

  Object.keys(capture.paramsRaw || {}).forEach(k => {
    if (k !== "sign" && k !== "signDate") {
      params[k] = capture.paramsRaw[k];
    }
  });

  if (overrideDeviceId && params.uniquedeviceid) {
    params.uniquedeviceid = overrideDeviceId;
  }

  params.signDate = getUTCSignDate();

  const signBase = Object.keys(params)
    .sort()
    .map(k => `${k}=${params[k]}`)
    .join("&");

  params.sign = md5(signBase + SECRET);

  return params;
}

function buildUrl(path, capture, overrideDeviceId) {
  const params = buildSignedParamsRaw(capture, overrideDeviceId);

  const qs = Object.keys(params)
    .map(k => `${k}=${encodeURIComponent(params[k])}`)
    .join("&");

  return `https://${API_HOST}/app/${path}?${qs}`;
}

function randHex(n) {
  let s = "";

  for (let i = 0; i < n; i++) {
    s += Math.floor(Math.random() * 16).toString(16);
  }

  return s.toUpperCase();
}

function genFakeDeviceId() {
  return `${randHex(8)}-${randHex(4)}-${randHex(4)}-${randHex(4)}-${randHex(12)}PingMeIOS`;
}

function cloneHeaders(headers) {
  const out = {};

  Object.keys(headers || {}).forEach(k => {
    out[k] = headers[k];
  });

  return out;
}

function buildHeaders(capture, ua) {
  const headers = cloneHeaders(capture.headers || {});

  delete headers["Content-Length"];
  delete headers["content-length"];
  delete headers[":authority"];
  delete headers[":method"];
  delete headers[":path"];
  delete headers[":scheme"];

  headers["Host"] = API_HOST;
  headers["Accept"] = headers["Accept"] || "application/json";

  Object.keys(headers).forEach(k => {
    const lk = k.toLowerCase();

    if (
      lk === "user-agent" ||
      lk === "connection" ||
      lk === "proxy-connection" ||
      lk === "keep-alive"
    ) {
      delete headers[k];
    }
  });

  headers["User-Agent"] = ua;
  headers["Connection"] = "close";

  return headers;
}

function normalizeAccount(raw, index) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("账号必须是 JSON 对象");
  }

  const capture = raw.capture || raw;

  if (
    !capture.paramsRaw ||
    typeof capture.paramsRaw !== "object" ||
    Array.isArray(capture.paramsRaw) ||
    !Object.keys(capture.paramsRaw).length
  ) {
    throw new Error("缺少有效的 paramsRaw");
  }

  const headers = capture.headers || {};

  const uaKey = Object.keys(headers).find(
    k => k.toLowerCase() === "user-agent"
  );

  return {
    ...raw,
    capture,
    baseUA: raw.baseUA || headers[uaKey] || "PingMe/1.9.3",
    uaSeed:
      Number.isInteger(raw.uaSeed) && raw.uaSeed >= 0
        ? raw.uaSeed
        : index
  };
}

function errorText(e) {
  // 避免把包含账号参数的完整请求 URL 写入日志。
  if (e.response) {
    return `HTTP ${e.response.status}`;
  }

  return e.code
    ? `网络请求失败 (${e.code})`
    : "请求失败";
}

async function fetchApi(path, account, headers, overrideDeviceId) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    let resp;

    try {
      resp = await axios.get(
        buildUrl(path, account.capture, overrideDeviceId),
        {
          headers,
          timeout: 20000
        }
      );
    } catch (e) {
      const retryable =
        !e.response &&
        /SSL|timeout|timed out|reset|connection|network|stream closed|closed|EOF|ECONN|ETIMEDOUT|EAI_AGAIN/i.test(
          `${e.code || ""} ${e.message || ""}`
        );

      if (attempt < 3 && retryable) {
        await sleep(1500);
        continue;
      }

      throw new Error(errorText(e));
    }

    let data = resp.data;

    if (typeof data === "string") {
      try {
        data = JSON.parse(data);
      } catch {
        return {
          retcode: -1,
          retmsg: "响应不是有效 JSON"
        };
      }
    }

    if (
      !data ||
      typeof data !== "object" ||
      Array.isArray(data) ||
      !("retcode" in data)
    ) {
      return {
        retcode: -1,
        retmsg: "响应格式异常，缺少 retcode"
      };
    }

    return data;
  }
}

function statusText(data) {
  return String(
    data.retmsg || `接口返回 retcode=${data.retcode}`
  );
}

function isDeregistered(data) {
  return statusText(data).includes("已被注销");
}

async function runAccount(account, index, total) {
  const tag = `[账号${index + 1}/${total} ${account.alias || "未命名"}]`;
  const msgs = [tag];

  try {
    const headers = buildHeaders(
      account.capture,
      buildUA(account.baseUA, account.uaSeed)
    );

    // 与 QX 一致：每账号每轮生成一次，仅视频请求使用。
    const fakeDeviceId = genFakeDeviceId();

    let deregistered = false;

    let data = await fetchApi(
      "queryBalanceAndBonus",
      account,
      headers
    );

    if (data.retcode === 0) {
      msgs.push(
        `💰 当前余额：${data.result?.balance ?? 0} Coins`
      );
    } else {
      msgs.push(`⚠️ 查询失败：${statusText(data)}`);
      deregistered = isDeregistered(data);
    }

    if (!deregistered) {
      data = await fetchApi("checkIn", account, headers);

      if (data.retcode === 0) {
        const hint = String(
          data.result?.bonusHint || data.retmsg || ""
        ).replace(/\n/g, " ");

        msgs.push(`✅ 签到成功：${hint}`);
      } else {
        msgs.push(`⚠️ 签到状态：${statusText(data)}`);
        deregistered = isDeregistered(data);
      }
    }

    if (deregistered) {
      msgs.push("🗑 账号已注销，本轮跳过；原 Secrets 保留");
    } else {
      for (let i = 1; i <= MAX_VIDEO; i++) {
        await sleep(i === 1 ? 1500 : VIDEO_DELAY);

        try {
          data = await fetchApi(
            "videoBonus",
            account,
            headers,
            fakeDeviceId
          );

          if (data.retcode === 0) {
            msgs.push(
              `🎬 视频${i}：+${data.result?.bonus ?? "?"} Coins`
            );
          } else {
            msgs.push(`⏸ 视频${i}：${statusText(data)}`);
            break;
          }
        } catch (e) {
          msgs.push(`❌ 视频${i}：${e.message}`);
          break;
        }
      }

      data = await fetchApi(
        "queryBalanceAndBonus",
        account,
        headers
      );

      if (data.retcode === 0) {
        msgs.push(
          `💰 最新余额：${data.result?.balance ?? 0} Coins`
        );
      } else {
        msgs.push(
          `⚠️ 最新余额查询失败：${statusText(data)}`
        );
      }
    }
  } catch (e) {
    msgs.push(`❌ 账号异常：${e.message || "执行失败"}`);
  }

  const text = msgs.join("\n");
  console.log(text);

  return text;
}

async function sendTG(title, content) {
  if (!TG_BOT_TOKEN || !TG_USER_ID) {
    console.log("未配置 TG 推送");
    return;
  }

  // 使用纯文本，并分段发送长通知。
  const chars = Array.from(`${title}\n\n${content}`);

  for (let i = 0; i < chars.length; i += 2000) {
    try {
      const resp = await axios.post(
        `https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage`,
        {
          chat_id: TG_USER_ID,
          text: chars.slice(i, i + 2000).join(""),
          disable_web_page_preview: true
        },
        {
          timeout: 20000
        }
      );

      if (resp.data?.ok !== true) {
        throw new Error("推送响应异常");
      }
    } catch (e) {
      console.log(`❌ TG推送失败：${errorText(e)}`);
      return;
    }
  }

  console.log("✅ TG推送成功");
}

async function main() {
  const accounts = [];
  const results = [];

  const inputs = [
    process.env.PINGME_DATA_1,
    process.env.PINGME_DATA_2,
    process.env.PINGME_DATA_3,
    process.env.PINGME_DATA_4,
    process.env.PINGME_DATA_5
  ];

  inputs.forEach((item, index) => {
    if (!item || !item.trim()) return;

    let raw;

    try {
      raw = JSON.parse(item);
    } catch {
      results.push(
        `❌ PINGME_DATA_${index + 1}：JSON 格式错误`
      );
      return;
    }

    try {
      accounts.push(normalizeAccount(raw, index));
    } catch (e) {
      results.push(
        `❌ PINGME_DATA_${index + 1}：${e.message}`
      );
    }
  });

  if (!accounts.length) {
    results.push("❌ 没有可执行账号");

    console.log(results.join("\n"));

    await sendTG(
      "⚠️ PingMe 配置异常",
      results.join("\n")
    );

    process.exitCode = 1;
    return;
  }

  for (let i = 0; i < accounts.length; i++) {
    results.push(
      await runAccount(accounts[i], i, accounts.length)
    );

    if (i < accounts.length - 1) {
      await sleep(ACCOUNT_GAP);
    }
  }

  const finalMsg = results.join("\n————————————\n");

  console.log("全部任务执行完成\n" + finalMsg);

  await sendTG("🎉 PingMe 执行完成", finalMsg);
}

main().catch(() => {
  console.error("❌ PingMe 执行异常");
  process.exitCode = 1;
});
