export function normalizeDomain(value) {
	let domain = value.trim().toLowerCase();
	if (!domain) return null;
	try {
		domain = new URL(domain.includes("://") ? domain : `https://${domain}`).hostname;
	} catch {
		domain = domain.split("/")[0].split(":")[0];
	}
	domain = domain.replace(/^\.+|\.+$/g, "");
	return /^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$/i.test(domain) ? domain : null;
}

export function buildDomainFilteredQuery(query, includeDomains, excludeDomains) {
	const parts = [query];
	if (includeDomains.length === 1) {
		parts.push(`site:${includeDomains[0]}`);
	} else if (includeDomains.length > 1) {
		parts.push(`(${includeDomains.map((domain) => `site:${domain}`).join(" OR ")})`);
	}
	parts.push(...excludeDomains.map((domain) => `-site:${domain}`));
	return parts.join(" ");
}

export function matchesDomainFilters(url, includeDomains, excludeDomains) {
	let host;
	try { host = new URL(url).hostname.toLowerCase(); } catch { return false; }
	const matches = (domain) => host === domain || host.endsWith(`.${domain}`);
	return !excludeDomains.some(matches) && (includeDomains.length === 0 || includeDomains.some(matches));
}
