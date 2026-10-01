import { Readability } from "@mozilla/readability";
import { JSDOM } from "jsdom";
import TurndownService from "turndown";
import { gfm } from "turndown-plugin-gfm";
import { validateRemoteUrl } from "./ssrf.js";

const MAX_RESPONSE_BYTES = 5 * 1024 * 1024;
const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308]);

export function createImpit(Impit, timeoutMs = 15000) {
	// Impit uses followRedirects rather than the Fetch API's redirect option.
	// Keep redirects visible so each Location is SSRF-validated below.
	return new Impit({ browser: "chrome", timeout: timeoutMs, followRedirects: false });
}

export const browserHeaders = {
	"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf;q=0.9,*/*;q=0.8",
	"Accept-Language": "en-US,en;q=0.9",
	"Accept-Encoding": "gzip, deflate, br",
	"Sec-Fetch-Dest": "document",
	"Sec-Fetch-Mode": "navigate",
	"Sec-Fetch-Site": "none",
	"Sec-Fetch-User": "?1",
	"Upgrade-Insecure-Requests": "1",
};

export function htmlToMarkdown(html) {
	const turndown = new TurndownService({ headingStyle: "atx", codeBlockStyle: "fenced" });
	turndown.use(gfm);
	turndown.addRule("removeEmptyLinks", {
		filter: (node) => node.nodeName === "A" && !node.textContent?.trim(),
		replacement: () => "",
	});
	return turndown
		.turndown(html)
		.replace(/\[\\?\[\s*\\?\]\]\([^)]*\)/g, "")
		.replace(/ +/g, " ")
		.replace(/\s+,/g, ",")
		.replace(/\s+\./g, ".")
		.replace(/\n{3,}/g, "\n\n")
		.trim();
}

export function extractReadableContent(html, url) {
	const dom = new JSDOM(html, { url });
	const reader = new Readability(dom.window.document);
	const article = reader.parse();
	if (article?.content) {
		return { title: article.title || "", content: htmlToMarkdown(article.content) };
	}

	const fallbackDoc = new JSDOM(html, { url });
	const body = fallbackDoc.window.document;
	body.querySelectorAll("script, style, noscript, nav, header, footer, aside").forEach((el) => el.remove());
	const main = body.querySelector("main, article, [role='main'], .content, #content") || body.body;
	const content = main?.innerHTML ? htmlToMarkdown(main.innerHTML) : "";
	const title = body.querySelector("title")?.textContent?.trim() || "";
	if (content.length < 100) throw new Error("Could not extract readable content from this page");
	return { title, content };
}

async function limitedBytes(response, maxBytes) {
	const declaredSize = Number(response.headers.get("content-length"));
	if (Number.isFinite(declaredSize) && declaredSize > maxBytes) {
		throw new Error(`Response exceeds ${Math.floor(maxBytes / 1024 / 1024)}MB limit`);
	}
	const bytes = new Uint8Array(await response.arrayBuffer());
	if (bytes.byteLength > maxBytes) throw new Error(`Response exceeds ${Math.floor(maxBytes / 1024 / 1024)}MB limit`);
	return bytes;
}

export async function fetchValidated(impit, urlString, { timeoutMs = 15000, maxBytes = MAX_RESPONSE_BYTES, validateUrl = validateRemoteUrl } = {}) {
	let current = (await validateUrl(urlString)).toString();
	for (let redirects = 0; redirects <= 5; redirects++) {
		const response = await impit.fetch(current, { headers: browserHeaders, timeout: timeoutMs });
		if (!REDIRECT_STATUSES.has(response.status)) {
			if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
			return { response, url: current, bytes: await limitedBytes(response, maxBytes) };
		}
		const location = response.headers.get("location");
		if (!location) throw new Error(`HTTP ${response.status}: redirect has no Location header`);
		if (redirects === 5) throw new Error("Too many redirects fetching URL");
		current = (await validateUrl(new URL(location, current).toString())).toString();
	}
	throw new Error("Too many redirects fetching URL");
}

export function isPdf(url, contentType) {
	return /\.pdf(?:$|[?#])/i.test(url) || /^application\/pdf(?:;|$)/i.test(contentType || "");
}

export async function extractPdf(bytes) {
	try {
		const { getDocumentProxy, extractText } = await import("unpdf");
		const pdf = await getDocumentProxy(bytes);
		const result = await extractText(pdf, { mergePages: true });
		const text = typeof result.text === "string" ? result.text : Array.isArray(result.text) ? result.text.join("\n\n") : "";
		if (text.trim().length < 1) throw new Error("PDF contains no extractable text (it may be scanned)");
		return text.trim();
	} catch (err) {
		throw new Error(`Could not extract PDF text: ${err.message}`);
	}
}
