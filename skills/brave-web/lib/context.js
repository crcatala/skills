import { matchesDomainFilters } from "./domains.js";

export const CONTEXT_THRESHOLDS = ["strict", "balanced", "lenient", "disabled"];

const NAMED_ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

export function decodeEntities(text) {
	return text.replace(/&(?:#(\d+)|#x([\da-f]+)|(\w+));/gi, (match, dec, hex, name) => {
		if (name) return NAMED_ENTITIES[name.toLowerCase()] ?? match;
		const code = dec ? Number(dec) : Number.parseInt(hex, 16);
		try { return String.fromCodePoint(code); } catch { return match; }
	});
}

// Allowlist mode when includes are present (excludes are enforced locally on the
// results); otherwise one discard rule per excluded domain.
export function buildGoggles(includeDomains, excludeDomains) {
	if (includeDomains.length > 0) return ["$discard", ...includeDomains.map((domain) => `$site=${domain}`)].join("\n");
	if (excludeDomains.length > 0) return excludeDomains.map((domain) => `$discard,site=${domain}`).join("\n");
	return null;
}

export function buildContextParams({ query, country, freshness, numUrls, maxTokens, threshold, includeDomains, excludeDomains }) {
	const params = new URLSearchParams({
		q: query,
		country,
		count: String(Math.min(50, Math.max(numUrls * 2, 10))),
		maximum_number_of_urls: String(numUrls),
		maximum_number_of_tokens: String(maxTokens),
		context_threshold_mode: threshold,
	});
	if (freshness) params.append("freshness", freshness);
	const goggles = buildGoggles(includeDomains, excludeDomains);
	if (goggles) params.append("goggles", goggles);
	return params;
}

function sourceAge(source) {
	const ages = Array.isArray(source?.age) ? source.age : [];
	return ages.find((value) => /\bago$/i.test(value)) || ages[0] || "";
}

export function normalizeContextResults(data, includeDomains = [], excludeDomains = []) {
	const sources = data?.sources || {};
	return (data?.grounding?.generic || [])
		.filter((entry) => entry.url && matchesDomainFilters(entry.url, includeDomains, excludeDomains))
		.map((entry) => ({
			title: decodeEntities(entry.title || sources[entry.url]?.title || ""),
			link: entry.url,
			age: sourceAge(sources[entry.url]),
			snippets: (entry.snippets || []).map((snippet) => (typeof snippet === "string" ? snippet : JSON.stringify(snippet))),
		}));
}

export function formatContextResults(results) {
	return results
		.map((result, i) => {
			const lines = [`--- Source ${i + 1} ---`, `Title: ${result.title}`, `Link: ${result.link}`];
			if (result.age) lines.push(`Age: ${result.age}`);
			lines.push("Passages:", result.snippets.join("\n...\n"), "");
			return lines.join("\n");
		})
		.join("\n");
}

export function describeApiError(status, body) {
	if (/OPTION_NOT_IN_PLAN/.test(body)) {
		return `HTTP ${status}: this Brave API key's plan does not include the requested endpoint (LLM Context needs the Search plan). Use plain search without --context, or upgrade the plan at https://api-dashboard.search.brave.com/app/subscriptions/subscribe`;
	}
	return `HTTP ${status}\n${body}`;
}
