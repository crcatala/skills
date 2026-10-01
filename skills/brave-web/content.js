#!/usr/bin/env node

import { ensureDeps } from "./lib/deps.js";
ensureDeps(import.meta.dirname);

const { Impit } = await import("impit");
const { findPassages } = await import("./lib/find.js");
const { loadCachedUrl, loadContent, storeContent } = await import("./lib/cache.js");
const { createImpit, extractPdf, extractReadableContent, fetchValidated, isPdf } = await import("./lib/content.js");
const { fetchGitHubRepoOverview, githubGuidance } = await import("./lib/github.js");

const DEFAULT_LIMIT = 30_000;

function usage() {
	console.log(`Usage: content.js <url> [options]
       content.js --cache <id> [options]

Extracts readable web content as markdown, caches the full result for one hour,
and prints a bounded slice by default.

Options:
  --raw                    Return the exact textual HTTP body (no readability)
  --find <text>            Find exact/case-insensitive/fuzzy passages
  --find-mode <mode>       exact, case-insensitive (default), or fuzzy
  --offset <chars>         Start output at this character offset
  --limit <chars>          Output length (default: 30000, max: 100000)
  --cache <id>             Read a previous cached result instead of fetching
  --cache-ttl <seconds>    Reuse URL content cached up to this age; 0 forces live fetch (max: 3600)

Examples:
  content.js https://example.com/article
  content.js https://example.com/report.pdf
  content.js --cache a1b2c3d4e5f67890 --find "installation"
  content.js https://example.com/article --cache-ttl 900
  content.js --cache a1b2c3d4e5f67890 --offset 30000 --limit 30000`);
}

function readOption(args, name) {
	const index = args.indexOf(name);
	if (index === -1) return null;
	const value = args[index + 1];
	if (!value || value.startsWith("--")) throw new Error(`${name} requires a value`);
	args.splice(index, 2);
	return value;
}

function positiveInteger(value, name, fallback, maximum) {
	if (value === null) return fallback;
	if (!/^\d+$/.test(value)) throw new Error(`${name} must be a non-negative integer`);
	return Math.min(Number(value), maximum);
}

function printEntry(entry, { findText, findMode, offset, limit }) {
	console.log(`# ${entry.title || "Extracted content"}\n`);
	console.log(`Source: ${entry.url}`);
	console.log(`Cache-ID: ${entry.id}\n`);
	if (findText) {
		console.log(findPassages(entry.content, findText, findMode).output);
		return;
	}
	const slice = entry.content.slice(offset, offset + limit);
	console.log(slice);
	if (offset + limit < entry.content.length) {
		console.log(`\n[Showing chars ${offset}-${offset + slice.length} of ${entry.content.length}. Continue with: content.js --cache ${entry.id} --offset ${offset + slice.length}]`);
	}
}

try {
	const args = process.argv.slice(2);
	if (args.includes("--help") || args.includes("-h")) {
		usage();
		process.exit(0);
	}

	const raw = args.includes("--raw");
	if (raw) args.splice(args.indexOf("--raw"), 1);
	const cacheId = readOption(args, "--cache");
	const cacheTtlSeconds = readOption(args, "--cache-ttl");
	const cacheTtlMs = cacheTtlSeconds === null ? null : positiveInteger(cacheTtlSeconds, "--cache-ttl", 0, 3_600) * 1000;
	const findText = readOption(args, "--find");
	const findMode = readOption(args, "--find-mode") || "case-insensitive";
	if (!["exact", "case-insensitive", "fuzzy"].includes(findMode)) throw new Error("--find-mode must be exact, case-insensitive, or fuzzy");
	const hasOffset = args.includes("--offset");
	const hasLimit = args.includes("--limit");
	const offset = positiveInteger(readOption(args, "--offset"), "--offset", 0, Number.MAX_SAFE_INTEGER);
	const limit = positiveInteger(readOption(args, "--limit"), "--limit", DEFAULT_LIMIT, 100_000);
	if (findText && (hasOffset || hasLimit)) throw new Error("--find cannot be combined with --offset or --limit");
	if (cacheId && args.length > 0) throw new Error("Provide either a URL or --cache, not both");
	if (!cacheId && args.length !== 1) {
		usage();
		process.exit(1);
	}

	if (cacheId) {
		printEntry(loadContent(cacheId, cacheTtlMs === null ? {} : { ttlMs: cacheTtlMs }), { findText, findMode, offset, limit });
		process.exit(0);
	}

	const url = args[0];
	if (cacheTtlMs !== null) {
		const cached = loadCachedUrl(url, { ttlMs: cacheTtlMs });
		if (cached) {
			printEntry(cached, { findText, findMode, offset, limit });
			process.exit(0);
		}
	}
	const githubResult = fetchGitHubRepoOverview(url) || githubGuidance(url);
	if (githubResult) {
		console.log(githubResult);
		process.exit(0);
	}

	const impit = createImpit(Impit);
	const { response, url: finalUrl, bytes } = await fetchValidated(impit, url);
	const contentType = response.headers.get("content-type") || "";
	let title = "";
	let content;
	if (isPdf(finalUrl, contentType)) {
		content = await extractPdf(bytes);
		title = finalUrl.split("/").pop()?.replace(/\.pdf(?:[?#].*)?$/i, "") || "PDF";
	} else {
		const body = new TextDecoder().decode(bytes);
		if (raw) {
			if (!/^(text\/|application\/(json|xml|javascript))/i.test(contentType)) {
				throw new Error(`--raw only supports textual responses (got ${contentType || "unknown content type"})`);
			}
			content = body;
			title = "Raw response";
		} else {
			({ title, content } = extractReadableContent(body, finalUrl));
		}
	}
	printEntry(storeContent({
		url: finalUrl,
		aliases: [url],
		title,
		content,
		contentType,
		etag: response.headers.get("etag"),
		lastModified: response.headers.get("last-modified"),
	}), { findText, findMode, offset, limit });
} catch (error) {
	console.error(`Error: ${error.message}`);
	process.exit(1);
}
