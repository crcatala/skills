import { lookup as dnsLookup } from "node:dns/promises";
import net from "node:net";

const BLOCKED_HOST_SUFFIXES = [".localhost", ".local", ".internal", ".lan", ".home.arpa", ".localdomain"];
const BLOCKED_HOSTS = new Set([
	"localhost",
	"localhost.localdomain",
	"metadata.google.internal",
	"metadata.goog",
	"kubernetes.default",
	"kubernetes.default.svc",
]);

function ipv4ToInt(address) {
	const parts = address.split(".").map((part) => Number(part));
	if (parts.length !== 4 || parts.some((part) => !Number.isInteger(part) || part < 0 || part > 255)) {
		return null;
	}
	return ((parts[0] << 24) >>> 0) + (parts[1] << 16) + (parts[2] << 8) + parts[3];
}

function inCidrV4(address, cidr, bits) {
	const ip = ipv4ToInt(address);
	const base = ipv4ToInt(cidr);
	if (ip === null || base === null) return false;
	const mask = bits === 0 ? 0 : (~0 << (32 - bits)) >>> 0;
	return (ip & mask) === (base & mask);
}

function ipv6EmbeddedIpv4(address) {
	const normalized = address.toLowerCase();
	const separator = normalized.indexOf("::");
	if (separator !== -1 && normalized.indexOf("::", separator + 1) !== -1) return null;
	const parseSide = (side) => {
		if (!side) return [];
		const tokens = side.split(":");
		const groups = [];
		for (let index = 0; index < tokens.length; index++) {
			const token = tokens[index];
			if (token.includes(".")) {
				const ipv4 = ipv4ToInt(token);
				if (ipv4 === null || index !== tokens.length - 1) return null;
				groups.push(ipv4 >>> 16, ipv4 & 0xffff);
			} else if (/^[0-9a-f]{1,4}$/i.test(token)) {
				groups.push(parseInt(token, 16));
			} else {
				return null;
			}
		}
		return groups;
	};
	const left = parseSide(separator === -1 ? normalized : normalized.slice(0, separator));
	const right = parseSide(separator === -1 ? "" : normalized.slice(separator + 2));
	if (!left || !right) return null;
	const missing = separator === -1 ? 0 : 8 - left.length - right.length;
	if (missing < 0 || (separator === -1 && left.length !== 8)) return null;
	const groups = [...left, ...Array(missing).fill(0), ...right];
	if (groups.length !== 8) return null;
	// IPv4-compatible (::w.x.y.z) and IPv4-mapped (::ffff:w.x.y.z) forms
	// can arrive as hexadecimal groups after URL normalization.
	const compatible = groups.slice(0, 6).every((group) => group === 0);
	const mapped = groups.slice(0, 5).every((group) => group === 0) && groups[5] === 0xffff;
	if (!compatible && !mapped) return null;
	return `${groups[6] >>> 8}.${groups[6] & 0xff}.${groups[7] >>> 8}.${groups[7] & 0xff}`;
}

export function isPrivateIp(address) {
	const embeddedIpv4 = ipv6EmbeddedIpv4(address);
	if (embeddedIpv4) return isPrivateIp(embeddedIpv4);

	const family = net.isIP(address);
	if (family === 4) {
		return (
			inCidrV4(address, "0.0.0.0", 8) ||
			inCidrV4(address, "10.0.0.0", 8) ||
			inCidrV4(address, "100.64.0.0", 10) ||
			inCidrV4(address, "127.0.0.0", 8) ||
			inCidrV4(address, "169.254.0.0", 16) ||
			inCidrV4(address, "172.16.0.0", 12) ||
			inCidrV4(address, "192.0.0.0", 24) ||
			inCidrV4(address, "192.0.2.0", 24) ||
			inCidrV4(address, "192.168.0.0", 16) ||
			inCidrV4(address, "198.18.0.0", 15) ||
			inCidrV4(address, "198.51.100.0", 24) ||
			inCidrV4(address, "203.0.113.0", 24) ||
			inCidrV4(address, "224.0.0.0", 4) ||
			inCidrV4(address, "240.0.0.0", 4)
		);
	}

	if (family === 6) {
		const normalized = address.toLowerCase();
		if (normalized === "::" || normalized === "::1") return true;
		const first = normalized.split(":")[0];
		const prefix = parseInt(first, 16);
		if (Number.isFinite(prefix) && (prefix & 0xfe00) === 0xfc00) return true; // fc00::/7
		if (Number.isFinite(prefix) && (prefix & 0xffc0) === 0xfe80) return true; // fe80::/10
		if (Number.isFinite(prefix) && (prefix & 0xff00) === 0xff00) return true; // ff00::/8
		if (normalized.startsWith("2001:db8:")) return true;
		return false;
	}

	return false;
}

function hostnameBlocked(hostname) {
	const host = hostname.replace(/^\[|\]$/g, "").toLowerCase();
	if (BLOCKED_HOSTS.has(host)) return true;
	return BLOCKED_HOST_SUFFIXES.some((suffix) => host.endsWith(suffix));
}

async function defaultLookup(hostname) {
	return dnsLookup(hostname, { all: true });
}

export async function validateRemoteUrl(urlString, { lookupFn = defaultLookup } = {}) {
	let url;
	try {
		url = new URL(urlString);
	} catch {
		throw new Error(`Invalid URL: ${urlString}`);
	}

	if (url.protocol !== "http:" && url.protocol !== "https:") {
		throw new Error(`Only HTTP and HTTPS URLs can be fetched (got ${url.protocol})`);
	}
	if (!url.hostname) {
		throw new Error("URL must include a hostname");
	}

	const hostname = url.hostname.replace(/^\[|\]$/g, "");
	if (hostnameBlocked(hostname)) {
		throw new Error(`Blocked hostname: ${hostname}`);
	}

	if (net.isIP(hostname)) {
		if (isPrivateIp(hostname)) {
			throw new Error(`Blocked private/reserved IP: ${hostname}`);
		}
		return url;
	}

	let addresses;
	try {
		addresses = await lookupFn(hostname);
	} catch (err) {
		throw new Error(`Failed to resolve ${hostname}: ${err.message}`);
	}

	if (!addresses?.length) {
		throw new Error(`Failed to resolve ${hostname}`);
	}

	for (const entry of addresses) {
		const address = typeof entry === "string" ? entry : entry.address;
		if (isPrivateIp(address)) {
			throw new Error(`Blocked hostname ${hostname} (resolves to private/reserved IP ${address})`);
		}
	}

	return url;
}
