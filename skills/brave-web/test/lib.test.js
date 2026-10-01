import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { loadCachedUrl, loadContent, pruneCache, storeContent } from "../lib/cache.js";
import { buildContextParams, buildGoggles, decodeEntities, describeApiError, formatContextResults, normalizeContextResults } from "../lib/context.js";
import { createImpit, extractReadableContent, fetchValidated } from "../lib/content.js";
import { findPassages } from "../lib/find.js";
import { githubGuidance, parseGitHubUrl } from "../lib/github.js";
import { buildDomainFilteredQuery, matchesDomainFilters, normalizeDomain } from "../lib/domains.js";
import { isPrivateIp, validateRemoteUrl } from "../lib/ssrf.js";

test("normalizes and locally enforces domain filters", () => {
	assert.equal(normalizeDomain("https://Docs.Example.com/guide"), "docs.example.com");
	assert.equal(normalizeDomain("not a domain"), null);
	assert.equal(matchesDomainFilters("https://api.docs.example.com/v1", ["example.com"], []), true);
	assert.equal(matchesDomainFilters("https://example.com", ["docs.example.com"], []), false);
	assert.equal(matchesDomainFilters("https://news.example.com", [], ["example.com"]), false);
	assert.equal(
		buildDomainFilteredQuery("React useEffect", ["react.dev", "developer.mozilla.org"], ["reddit.com"]),
		"React useEffect (site:react.dev OR site:developer.mozilla.org) -site:reddit.com",
	);
});

test("identifies private, reserved, and public IPs", () => {
	for (const address of ["127.0.0.1", "10.1.2.3", "169.254.169.254", "172.16.1.1", "192.168.1.1", "::1", "fc00::1", "fe80::1", "::ffff:127.0.0.1", "::ffff:7f00:1", "0:0:0:0:0:ffff:0a00:1"]) {
		assert.equal(isPrivateIp(address), true, address);
	}
	assert.equal(isPrivateIp("8.8.8.8"), false);
	assert.equal(isPrivateIp("2606:4700:4700::1111"), false);
});

test("SSRF validator rejects private DNS answers and validates public ones", async () => {
	await assert.rejects(validateRemoteUrl("http://localhost/"), /Blocked hostname/);
	await assert.rejects(validateRemoteUrl("http://[::ffff:127.0.0.1]/"), /private\/reserved/);
	await assert.rejects(validateRemoteUrl("http://[::ffff:7f00:1]/"), /private\/reserved/);
	await assert.rejects(validateRemoteUrl("http://example.test/", { lookupFn: async () => [{ address: "127.0.0.1" }] }), /private\/reserved/);
	const url = await validateRemoteUrl("https://example.test/path", { lookupFn: async () => [{ address: "93.184.216.34" }] });
	assert.equal(url.toString(), "https://example.test/path");
});

test("cache stores full content, expires entries, and honors its ID contract", () => {
	const original = process.env.BRAVE_WEB_CACHE_DIR;
	const dir = mkdtempSync(path.join(os.tmpdir(), "brave-web-test-"));
	process.env.BRAVE_WEB_CACHE_DIR = dir;
	try {
		const entry = storeContent({ url: "https://example.com/article", title: "Article", content: "full content" });
		assert.match(entry.id, /^[a-f0-9]{16}$/);
		assert.equal(loadContent(entry.id).content, "full content");
		assert.throws(() => loadContent("../../etc/passwd"), /Invalid cache ID/);
		pruneCache({ now: Date.now() + 7_200_000, ttlMs: 3_600_000 });
		assert.throws(() => loadContent(entry.id), /No cached content/);
	} finally {
		if (original === undefined) delete process.env.BRAVE_WEB_CACHE_DIR;
		else process.env.BRAVE_WEB_CACHE_DIR = original;
		rmSync(dir, { recursive: true, force: true });
	}
});

test("cache lookup honors a caller-provided freshness window", () => {
	const original = process.env.BRAVE_WEB_CACHE_DIR;
	const dir = mkdtempSync(path.join(os.tmpdir(), "brave-web-test-"));
	process.env.BRAVE_WEB_CACHE_DIR = dir;
	try {
		const entry = storeContent({
			url: "https://example.com/current/",
			aliases: ["http://example.com/current"],
			content: "current content",
			etag: "etag-value",
			lastModified: "Mon, 01 Jan 2024 00:00:00 GMT",
		});
		assert.equal(loadCachedUrl(entry.url, { ttlMs: 60_000 })?.content, "current content");
		assert.equal(loadCachedUrl("http://example.com/current", { ttlMs: 60_000 })?.id, entry.id);
		assert.equal(loadCachedUrl(entry.url, { ttlMs: 0 }), null);
		assert.equal(loadCachedUrl(entry.url, { now: Date.now() + 60_001, ttlMs: 60_000 }), null);
		assert.throws(() => loadContent(entry.id, { now: Date.now() + 60_001, ttlMs: 60_000 }), /has expired/);
		assert.equal(loadContent(entry.id).etag, "etag-value");
	} finally {
		if (original === undefined) delete process.env.BRAVE_WEB_CACHE_DIR;
		else process.env.BRAVE_WEB_CACHE_DIR = original;
		rmSync(dir, { recursive: true, force: true });
	}
});

test("cache retains no more than 32 entries", () => {
	const original = process.env.BRAVE_WEB_CACHE_DIR;
	const dir = mkdtempSync(path.join(os.tmpdir(), "brave-web-test-"));
	process.env.BRAVE_WEB_CACHE_DIR = dir;
	try {
		for (let index = 0; index < 33; index++) {
			storeContent({ url: `https://example.com/${index}`, content: `content ${index}` });
		}
		assert.equal(readdirSync(dir).filter((name) => /^[a-f0-9]{16}\.json$/.test(name)).length, 32);
	} finally {
		if (original === undefined) delete process.env.BRAVE_WEB_CACHE_DIR;
		else process.env.BRAVE_WEB_CACHE_DIR = original;
		rmSync(dir, { recursive: true, force: true });
	}
});

test("disables Impit automatic redirects and validates each redirect target", async () => {
	let options;
	class FakeImpit { constructor(value) { options = value; } }
	createImpit(FakeImpit);
	assert.equal(options.followRedirects, false);

	const calls = [];
	const impit = { fetch: async (url) => {
		calls.push(url);
		return { status: 302, headers: { get: (name) => name === "location" ? "http://127.0.0.1/metadata" : null } };
	} };
	const validateUrl = async (url) => {
		if (url.includes("127.0.0.1")) throw new Error("Blocked private/reserved IP");
		return new URL(url);
	};
	await assert.rejects(fetchValidated(impit, "https://public.example/", { validateUrl }), /Blocked private\/reserved/);
	assert.deepEqual(calls, ["https://public.example/"]);
});

test("passage finder returns bounded nearby context", () => {
	const text = "First paragraph.\n\nThe installation requires a retry timeout setting.\n\nLast paragraph.";
	const found = findPassages(text, "installation", "case-insensitive");
	assert.equal(found.count, 1);
	assert.match(found.output, /retry timeout/);
	assert.equal(findPassages(text, "instalation", "fuzzy").count, 1);
});

test("readability extracts article content", () => {
	const extracted = extractReadableContent("<html><head><title>Guide</title></head><body><article><h1>Guide</h1><p>This is a sufficiently long article paragraph that explains how to configure the guide and includes enough prose for the extractor to consider it readable.</p></article></body></html>", "https://example.com/guide");
	assert.equal(extracted.title, "Guide");
	assert.match(extracted.content, /sufficiently long/);
});

test("GitHub URLs return gh-first guidance instead of HTML scraping", () => {
	assert.deepEqual(parseGitHubUrl("https://github.com/owner/repo/blob/main/README.md"), { owner: "owner", repo: "repo", view: "blob", ref: "main", path: ["README.md"] });
	assert.match(githubGuidance("https://github.com/owner/repo"), /gh repo view owner\/repo/);
	assert.equal(githubGuidance("https://github.com/owner/repo/issues/2"), null);
});

test("decodes HTML entities left in Brave snippets", () => {
	assert.equal(decodeEntities("can&#x27;t &amp; won&#39;t &lt;b&gt; &quot;x&quot; &unknown; &#xZZ;"), "can't & won't <b> \"x\" &unknown; &#xZZ;");
	assert.equal(decodeEntities("&#99999999999;"), "&#99999999999;");
});

test("builds LLM Context goggles and request parameters", () => {
	assert.equal(buildGoggles([], []), null);
	assert.equal(buildGoggles(["docs.rs", "crates.io"], ["example.com"]), "$discard\n$site=docs.rs\n$site=crates.io");
	assert.equal(buildGoggles([], ["a.com", "b.org"]), "$discard,site=a.com\n$discard,site=b.org");
	const params = buildContextParams({ query: "q", country: "US", freshness: "pw", numUrls: 5, maxTokens: 4096, threshold: "strict", includeDomains: [], excludeDomains: ["a.com"] });
	assert.equal(params.get("maximum_number_of_urls"), "5");
	assert.equal(params.get("maximum_number_of_tokens"), "4096");
	assert.equal(params.get("context_threshold_mode"), "strict");
	assert.equal(params.get("freshness"), "pw");
	assert.equal(params.get("goggles"), "$discard,site=a.com");
	assert.equal(params.get("count"), "10");
	assert.equal(buildContextParams({ query: "q", country: "US", numUrls: 50, maxTokens: 1024, threshold: "lenient", includeDomains: [], excludeDomains: [] }).get("count"), "50");
});

test("normalizes LLM Context responses and enforces domain filters locally", () => {
	const data = {
		grounding: {
			generic: [
				{ url: "https://docs.example.com/a", title: "A &amp; B", snippets: ["one", "two"] },
				{ url: "https://bad.example.org/x", title: "Bad", snippets: ["no"] },
				{ url: "https://docs.example.com/b", snippets: [] },
			],
		},
		sources: {
			"https://docs.example.com/a": { age: ["Friday, September 25, 2026", "2026-09-25", "6 days ago"] },
			"https://docs.example.com/b": { title: "From sources" },
		},
	};
	const results = normalizeContextResults(data, [], ["example.org"]);
	assert.deepEqual(results.map((result) => result.link), ["https://docs.example.com/a", "https://docs.example.com/b"]);
	assert.equal(results[0].title, "A & B");
	assert.equal(results[0].age, "6 days ago");
	assert.equal(results[1].title, "From sources");
	assert.deepEqual(normalizeContextResults({}, [], []), []);
	assert.match(formatContextResults(results), /--- Source 1 ---\nTitle: A & B\nLink: https:\/\/docs\.example\.com\/a\nAge: 6 days ago\nPassages:\none\n\.\.\.\ntwo/);
});

test("explains plan errors for the LLM Context endpoint", () => {
	assert.match(describeApiError(400, '{"code":"OPTION_NOT_IN_PLAN"}'), /does not include/);
	assert.match(describeApiError(500, "boom"), /^HTTP 500\nboom$/);
});
