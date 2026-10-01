import { createHash } from "node:crypto";
import { chmodSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const DEFAULT_TTL_MS = 60 * 60 * 1000;
const DEFAULT_MAX_ENTRIES = 32;

export const DEFAULT_CACHE_TTL_MS = DEFAULT_TTL_MS;

export function cacheDirectory() {
	return process.env.BRAVE_WEB_CACHE_DIR || "/tmp/brave-web-cache";
}

function ensureCacheDirectory() {
	const dir = cacheDirectory();
	mkdirSync(dir, { recursive: true, mode: 0o700 });
	try { chmodSync(dir, 0o700); } catch { /* best effort on non-POSIX systems */ }
	return dir;
}

function cachePath(id) {
	if (!/^[a-f0-9]{16}$/i.test(id)) throw new Error("Invalid cache ID");
	return join(cacheDirectory(), `${id}.json`);
}

function entryId(url) {
	return createHash("sha256").update(url).digest("hex").slice(0, 16);
}

export function pruneCache({ now = Date.now(), ttlMs = DEFAULT_TTL_MS, maxEntries = DEFAULT_MAX_ENTRIES } = {}) {
	const dir = ensureCacheDirectory();
	const entries = [];
	for (const name of readdirSync(dir)) {
		if (!/^[a-f0-9]{16}\.json$/i.test(name)) continue;
		const path = join(dir, name);
		try {
			const stat = statSync(path);
			if (now - stat.mtimeMs > ttlMs) {
				rmSync(path, { force: true });
				continue;
			}
			entries.push({ path, mtimeMs: stat.mtimeMs });
		} catch { /* a concurrent cleanup won the race */ }
	}
	entries.sort((a, b) => a.mtimeMs - b.mtimeMs);
	for (const entry of entries.slice(0, Math.max(0, entries.length - maxEntries))) {
		rmSync(entry.path, { force: true });
	}
}

export function storeContent({ url, aliases = [], title = "", content, contentType = "text/html", etag = null, lastModified = null }) {
	if (typeof content !== "string" || content.length === 0) throw new Error("Cannot cache empty content");
	const dir = ensureCacheDirectory();
	pruneCache();
	const id = entryId(url);
	const fetchedAt = new Date().toISOString();
	const normalizedAliases = [...new Set([url, ...aliases].filter((alias) => typeof alias === "string" && alias))];
	const entry = { id, url, aliases: normalizedAliases, title, content, contentType, etag, lastModified, fetchedAt, createdAt: fetchedAt };
	const path = join(dir, `${id}.json`);
	writeFileSync(path, JSON.stringify(entry), { mode: 0o600 });
	try { chmodSync(path, 0o600); } catch { /* best effort on non-POSIX systems */ }
	// Enforce the cap after adding a new URL; a pre-write prune alone permits 33 entries.
	pruneCache();
	return entry;
}

export function loadCachedUrl(url, { now = Date.now(), ttlMs = DEFAULT_CACHE_TTL_MS } = {}) {
	if (!Number.isFinite(ttlMs) || ttlMs < 0) throw new Error("Cache TTL must be a non-negative number");
	if (ttlMs === 0) return null;
	const effectiveTtlMs = Math.min(ttlMs, DEFAULT_CACHE_TTL_MS);
	let names;
	try {
		names = readdirSync(cacheDirectory());
	} catch {
		return null;
	}
	for (const name of names) {
		if (!/^[a-f0-9]{16}\.json$/i.test(name)) continue;
		const path = join(cacheDirectory(), name);
		try {
			const stat = statSync(path);
			if (now - stat.mtimeMs > effectiveTtlMs) continue;
			const parsed = JSON.parse(readFileSync(path, "utf8"));
			const aliases = Array.isArray(parsed?.aliases) ? parsed.aliases : [parsed?.url];
			if (typeof parsed?.content === "string" && aliases.includes(url)) return parsed;
		} catch { /* skip malformed or concurrently removed entries */ }
	}
	return null;
}

export function loadContent(id, { now = Date.now(), ttlMs = DEFAULT_TTL_MS } = {}) {
	const path = cachePath(id);
	let stat;
	try {
		stat = statSync(path);
	} catch {
		throw new Error(`No cached content found for ID ${id}`);
	}
	const ageMs = now - stat.mtimeMs;
	if (ageMs > ttlMs || ageMs > DEFAULT_TTL_MS) {
		// A caller's shorter freshness requirement is a cache miss, not a retention-policy change.
		if (ageMs > DEFAULT_TTL_MS) rmSync(path, { force: true });
		throw new Error(`Cached content ${id} has expired`);
	}
	try {
		const parsed = JSON.parse(readFileSync(path, "utf8"));
		if (parsed?.id !== id || typeof parsed.content !== "string" || typeof parsed.url !== "string") {
			throw new Error("invalid cache entry");
		}
		return parsed;
	} catch (err) {
		if (err.message === "invalid cache entry") throw new Error(`Cached content ${id} is invalid`);
		throw err;
	}
}
