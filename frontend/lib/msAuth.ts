import { apiFetch } from "./api";

const STATE_KEY = "ms_oauth_state";
const VERIFIER_KEY = "ms_oauth_verifier";

type MsConfig = {
  ms_client_id?: string | null;
  ms_tenant_id?: string | null;
};

const base64UrlEncode = (buffer: ArrayBuffer) => {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
};

const randomString = (length: number) => {
  const array = new Uint8Array(length);
  crypto.getRandomValues(array);
  return Array.from(array, (byte) => ("0" + byte.toString(16)).slice(-2)).join("");
};

const sha256Hex = (ascii: string) => {
  const maxWord = Math.pow(2, 32);
  let result = "";

  const words: number[] = [];
  const asciiBitLength = ascii.length * 8;

  let hash: number[] = [];
  const k: number[] = [];
  let i = 0;
  let j = 0;
  let prime = 2;
  while (hash.length < 8) {
    let isPrime = true;
    for (let factor = 2; factor * factor <= prime; factor += 1) {
      if (prime % factor === 0) {
        isPrime = false;
        break;
      }
    }
    if (isPrime) {
      hash.push((Math.pow(prime, 0.5) * maxWord) | 0);
      k.push((Math.pow(prime, 1 / 3) * maxWord) | 0);
    }
    prime += 1;
  }

  const padded = ascii + "\x80";
  for (i = 0; i < padded.length; i += 1) {
    j = padded.charCodeAt(i);
    words[i >> 2] |= j << ((3 - i) % 4) * 8;
  }
  words[(asciiBitLength >> 5) | 15] = asciiBitLength;

  const w = new Array(64);
  for (i = 0; i < words.length; i += 16) {
    const oldHash = hash.slice(0);
    for (j = 0; j < 64; j += 1) {
      const a = hash[0];
      const e = hash[4];
      let wj = words[i + j];
      if (j >= 16) {
        const sigma0 =
          ((w[j - 15] >>> 7) | (w[j - 15] << 25)) ^
          ((w[j - 15] >>> 18) | (w[j - 15] << 14)) ^
          (w[j - 15] >>> 3);
        const sigma1 =
          ((w[j - 2] >>> 17) | (w[j - 2] << 15)) ^
          ((w[j - 2] >>> 19) | (w[j - 2] << 13)) ^
          (w[j - 2] >>> 10);
        wj = (w[j - 16] + sigma0 + w[j - 7] + sigma1) | 0;
      }
      w[j] = wj;

      const sigma1 =
        ((e >>> 6) | (e << 26)) ^
        ((e >>> 11) | (e << 21)) ^
        ((e >>> 25) | (e << 7));
      const ch = (e & hash[5]) ^ (~e & hash[6]);
      const temp1 = (hash[7] + sigma1 + ch + k[j] + wj) | 0;

      const sigma0 =
        ((a >>> 2) | (a << 30)) ^
        ((a >>> 13) | (a << 19)) ^
        ((a >>> 22) | (a << 10));
      const maj = (a & hash[1]) ^ (a & hash[2]) ^ (hash[1] & hash[2]);
      const temp2 = (sigma0 + maj) | 0;

      hash = [(temp1 + temp2) | 0].concat(hash);
      hash[4] = (hash[4] + temp1) | 0;
      hash.pop();
    }
    for (j = 0; j < 8; j += 1) {
      hash[j] = (hash[j] + oldHash[j]) | 0;
    }
  }

  for (i = 0; i < 8; i += 1) {
    for (j = 3; j + 1; j -= 1) {
      const b = (hash[i] >> (j * 8)) & 255;
      result += (b < 16 ? "0" : "") + b.toString(16);
    }
  }
  return result;
};

const sha256Bytes = (value: string) => {
  const hex = sha256Hex(value);
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i += 1) {
    bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return bytes;
};

const pkceChallenge = async (verifier: string) => {
  const data = new TextEncoder().encode(verifier);
  if (typeof crypto !== "undefined" && crypto.subtle?.digest) {
    const digest = await crypto.subtle.digest("SHA-256", data);
    return base64UrlEncode(digest);
  }
  const digestBytes = sha256Bytes(verifier);
  return base64UrlEncode(digestBytes.buffer);
};

const getMsConfig = async () => {
  return apiFetch<MsConfig>("/api/config");
};

const fetchGroupMembership = async (accessToken: string) => {
  const groups: string[] = [];
  let url = "https://graph.microsoft.com/v1.0/me/memberOf?$select=id,displayName";
  while (url) {
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${accessToken}` }
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      const message =
        payload?.error?.message ||
        "Unable to read group membership. Admin consent may be required.";
      throw new Error(message);
    }
    const data = await response.json();
    const values = Array.isArray(data.value) ? data.value : [];
    values.forEach((entry: { id?: string; displayName?: string }) => {
      if (entry.displayName) {
        groups.push(entry.displayName);
      }
      if (entry.id) {
        groups.push(entry.id);
      }
    });
    url = data["@odata.nextLink"] || "";
  }
  return groups;
};

export const startMicrosoftLogin = async () => {
  const config = await getMsConfig();
  if (!config.ms_client_id) {
    throw new Error("Microsoft client ID is not configured.");
  }
  const tenant = config.ms_tenant_id || "common";
  const state = randomString(16);
  const verifier = randomString(64);
  const challenge = await pkceChallenge(verifier);
  sessionStorage.setItem(STATE_KEY, state);
  sessionStorage.setItem(VERIFIER_KEY, verifier);

  const redirectUri = `${window.location.origin}/auth/callback`;
  const params = new URLSearchParams({
    client_id: config.ms_client_id,
    response_type: "code",
    redirect_uri: redirectUri,
    response_mode: "query",
    scope: "openid profile email GroupMember.Read.All",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
    prompt: "select_account"
  });
  window.location.href = `https://login.microsoftonline.com/${tenant}/oauth2/v2.0/authorize?${params.toString()}`;
};

export const completeMicrosoftLogin = async (code: string, state: string) => {
  const storedState = sessionStorage.getItem(STATE_KEY);
  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  if (!storedState || storedState !== state) {
    throw new Error("Invalid OAuth state.");
  }
  if (!verifier) {
    throw new Error("Missing PKCE verifier.");
  }
  const config = await getMsConfig();
  if (!config.ms_client_id) {
    throw new Error("Microsoft client ID is not configured.");
  }
  const tenant = config.ms_tenant_id || "common";
  const redirectUri = `${window.location.origin}/auth/callback`;
  const body = new URLSearchParams({
    client_id: config.ms_client_id,
    scope: "openid profile email",
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
    code_verifier: verifier
  });

  const response = await fetch(
    `https://login.microsoftonline.com/${tenant}/oauth2/v2.0/token`,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body
    }
  );
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error_description || "Token exchange failed.");
  }
  if (!payload.id_token) {
    throw new Error("Missing id_token from Microsoft.");
  }

  const groups = payload.access_token
    ? await fetchGroupMembership(payload.access_token)
    : [];

  await apiFetch("/auth/token", {
    method: "POST",
    json: { id_token: payload.id_token, groups }
  });

  sessionStorage.removeItem(STATE_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);
};
