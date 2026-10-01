#!/usr/bin/env node

import { ensureDeps } from "./lib/deps.js";
ensureDeps(import.meta.dirname);

const { Impit } = await import("impit");
const { createImpit, extractPdf, extractReadableContent, fetchValidated, isPdf } = await import("./lib/content.js");
const { githubGuidance } = await import("./lib/github.js");
const { loadCachedUrl, storeContent } = await import("./lib/cache.js");
const { buildDomainFilteredQuery, matchesDomainFilters, normalizeDomain } = await import("./lib/domains.js");

const DEFAULT_CONTENT_LIMIT = 5_000;
const DEFAULT_CONTENT_CONCURRENCY = 3;
const DEFAULT_CONTENT_TIMEOUT_MS = 15_000;

function usage() {
	console.log(`Usage: search.js <query> [options]

Options:
  -n <num>                       Results (default: 5, max: 20)
  --content                      Fetch and include content for each result
  --content-limit <chars>        Content preview size (default: 5000, max: 100000)
  --content-concurrency <num>    Simultaneous content fetches (default: 3, max: 10)
  --content-timeout-ms <ms>      Per-page fetch timeout (default: 15000, max: 120000)
  --cache-ttl <seconds>          Reuse locally cached content up to this age; 0 forces live fetch
  --json                         Emit structured JSON
  --country <code>               Two-letter country code (default: US)
  --freshness <period>           pd, pw, pm, py, or YYYY-MM-DDtoYYYY-MM-DD
  --site <domain>                Restrict results to a domain (repeatable)
  --exclude-site <domain>        Exclude a domain (repeatable)

Examples:
  search.js "TypeScript decorators" --site typescriptlang.org
  search.js "AI news" --exclude-site reddit.com --freshness pw
  search.js "API retries" --site docs.example.com --content --content-limit 10000
  search.js "React hooks" --content --cache-ttl 3600 --json`);
}

function readOption(args, name) {
	const index = args.indexOf(name);
	if (index === -1) return null;
	const value = args[index + 1];
	if (!value || value.startsWith("-")) throw new Error(`${name} requires a value`);
	args.splice(index, 2);
	return value;
}

function readRepeatedOption(args, name) {
	const values = [];
	let value;
	while ((value = readOption(args, name)) !== null) values.push(value);
	return values;
}

function boundedInteger(value, name, fallback, minimum, maximum) {
	if (value === null) return fallback;
	if (!/^\d+$/.test(value)) throw new Error(`${name} must be an integer from ${minimum} to ${maximum}`);
	const number = Number(value);
	if (number < minimum || number > maximum) throw new Error(`${name} must be an integer from ${minimum} to ${maximum}`);
	return number;
}

async function fetchBraveResults(query, numResults, country, freshness, includeDomains, excludeDomains) {
	const apiKey = process.env.BRAVE_API_KEY;
	if (!apiKey) throw new Error("BRAVE_API_KEY environment variable is required. Get a key at https://api-dashboard.search.brave.com/app/keys");
	const hasDomainFilters = includeDomains.length > 0 || excludeDomains.length > 0;
	const params = new URLSearchParams({
		q: buildDomainFilteredQuery(query, includeDomains, excludeDomains),
		count: String(hasDomainFilters ? 20 : numResults),
		country,
	});
	if (freshness) params.append("freshness", freshness);
	const response = await fetch(`https://api.search.brave.com/res/v1/web/search?${params}`, {
		headers: { Accept: "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": apiKey },
	});
	if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}\n${await response.text()}`);
	const data = await response.json();
	return (data.web?.results || [])
		.map((result) => ({ title: result.title || "", link: result.url || "", snippet: result.description || "", age: result.age || result.page_age || "" }))
		.filter((result) => result.link && matchesDomainFilters(result.link, includeDomains, excludeDomains))
		.slice(0, numResults);
}

async function mapWithConcurrency(values, limit, callback) {
	const results = new Array(values.length);
	let next = 0;
	async function worker() {
		while (next < values.length) {
			const index = next++;
			results[index] = await callback(values[index]);
		}
	}
	await Promise.all(Array.from({ length: Math.min(limit, values.length) }, worker));
	return results;
}

const impit = createImpit(Impit);
async function fetchPageContent(url, { contentLimit, timeoutMs, cacheTtlMs }) {
	try {
		const github = githubGuidance(url);
		if (github) return { preview: github, cacheId: null, cached: false };
		const cached = cacheTtlMs === null ? null : loadCachedUrl(url, { ttlMs: cacheTtlMs });
		if (cached) return { preview: cached.content.slice(0, contentLimit), cacheId: cached.id, cached: true };
		const { response, url: finalUrl, bytes } = await fetchValidated(impit, url, { timeoutMs });
		const contentType = response.headers.get("content-type") || "";
		let title;
		let content;
		if (isPdf(finalUrl, contentType)) {
			content = await extractPdf(bytes);
			title = finalUrl.split("/").pop()?.replace(/\.pdf(?:[?#].*)?$/i, "") || "PDF";
		} else {
			({ title, content } = extractReadableContent(new TextDecoder().decode(bytes), finalUrl));
		}
		const entry = storeContent({
			url: finalUrl,
			aliases: [url],
			title,
			content,
			contentType,
			etag: response.headers.get("etag"),
			lastModified: response.headers.get("last-modified"),
		});
		return { preview: content.slice(0, contentLimit), cacheId: entry.id, cached: false };
	} catch (error) {
		return { preview: `(Error: ${error.message})`, cacheId: null, cached: false };
	}
}

try {
	const args = process.argv.slice(2);
	if (args.includes("--help") || args.includes("-h")) { usage(); process.exit(0); }
	const fetchContent = args.includes("--content");
	if (fetchContent) args.splice(args.indexOf("--content"), 1);
	const jsonOutput = args.includes("--json");
	if (jsonOutput) args.splice(args.indexOf("--json"), 1);
	const nValue = readOption(args, "-n");
	const numResults = boundedInteger(nValue, "-n", 5, 1, 20);
	const contentLimit = boundedInteger(readOption(args, "--content-limit"), "--content-limit", DEFAULT_CONTENT_LIMIT, 1, 100_000);
	const contentConcurrency = boundedInteger(readOption(args, "--content-concurrency"), "--content-concurrency", DEFAULT_CONTENT_CONCURRENCY, 1, 10);
	const contentTimeoutMs = boundedInteger(readOption(args, "--content-timeout-ms"), "--content-timeout-ms", DEFAULT_CONTENT_TIMEOUT_MS, 1_000, 120_000);
	const cacheTtlSeconds = readOption(args, "--cache-ttl");
	if (cacheTtlSeconds !== null && !fetchContent) throw new Error("--cache-ttl requires --content");
	const cacheTtlMs = cacheTtlSeconds === null ? null : boundedInteger(cacheTtlSeconds, "--cache-ttl", 0, 0, 31_536_000) * 1000;
	const country = (readOption(args, "--country") || "US").toUpperCase();
	if (!/^[A-Z]{2}$/.test(country)) throw new Error("--country must be a two-letter code");
	const freshness = readOption(args, "--freshness");
	const includeDomains = readRepeatedOption(args, "--site").map(normalizeDomain);
	const excludeDomains = readRepeatedOption(args, "--exclude-site").map(normalizeDomain);
	if ([...includeDomains, ...excludeDomains].some((domain) => !domain)) throw new Error("--site and --exclude-site values must be valid domains");
	const query = args.join(" ").trim();
	if (!query) { usage(); process.exit(1); }

	const results = await fetchBraveResults(query, numResults, country, freshness, includeDomains, excludeDomains);
	if (fetchContent) {
		const content = await mapWithConcurrency(results, contentConcurrency, (result) => fetchPageContent(result.link, { contentLimit, timeoutMs: contentTimeoutMs, cacheTtlMs }));
		for (let i = 0; i < results.length; i++) Object.assign(results[i], { content: content[i].preview, cacheId: content[i].cacheId, cached: content[i].cached });
	}
	if (jsonOutput) {
		console.log(JSON.stringify({ query, country, freshness: freshness || null, results }, null, 2));
		process.exit(0);
	}
	if (results.length === 0) { console.error("No results found."); process.exit(0); }
	for (let i = 0; i < results.length; i++) {
		const result = results[i];
		console.log(`--- Result ${i + 1} ---\nTitle: ${result.title}\nLink: ${result.link}`);
		if (result.age) console.log(`Age: ${result.age}`);
		console.log(`Snippet: ${result.snippet}`);
		if (result.content) console.log(`Content${result.cached ? " (cached)" : ""}:\n${result.content}`);
		if (result.cacheId) console.log(`Cache-ID: ${result.cacheId} (full content: content.js --cache ${result.cacheId})`);
		console.log("");
	}
} catch (error) {
	console.error(`Error: ${error.message}`);
	process.exit(1);
}
