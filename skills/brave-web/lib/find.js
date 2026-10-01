const CONTEXT_CHARS = 400;
const MAX_OUTPUT_CHARS = 20_000;

function normalize(value) {
	return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase();
}

function editDistanceWithin(left, right, maximum) {
	if (Math.abs(left.length - right.length) > maximum) return false;
	let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
	for (let i = 1; i <= left.length; i++) {
		const current = [i];
		let rowMinimum = i;
		for (let j = 1; j <= right.length; j++) {
			const value = Math.min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (left[i - 1] === right[j - 1] ? 0 : 1));
			current[j] = value;
			rowMinimum = Math.min(rowMinimum, value);
		}
		if (rowMinimum > maximum) return false;
		previous = current;
	}
	return previous[right.length] <= maximum;
}

function literalMatches(text, query, caseInsensitive) {
	const haystack = caseInsensitive ? text.toLocaleLowerCase() : text;
	const needle = caseInsensitive ? query.toLocaleLowerCase() : query;
	const matches = [];
	for (let start = haystack.indexOf(needle); start >= 0; start = haystack.indexOf(needle, start + Math.max(needle.length, 1))) {
		matches.push({ query, start, end: start + query.length });
	}
	return matches;
}

function fuzzyMatches(text, query) {
	const queryTokens = normalize(query).match(/[\p{L}\p{N}]+/gu) || [];
	if (queryTokens.length === 0) return [];
	const matches = [];
	for (const paragraph of text.matchAll(/[^\n]+(?:\n(?!\n)[^\n]+)*/g)) {
		if (paragraph.index === undefined) continue;
		const tokens = [...paragraph[0].matchAll(/[\p{L}\p{N}]+/gu)];
		const matched = queryTokens.filter((queryToken) => tokens.some((token) => {
			const maximum = queryToken.length >= 9 ? 2 : queryToken.length >= 5 ? 1 : 0;
			return editDistanceWithin(queryToken, normalize(token[0]), maximum);
		}));
		if (matched.length < (queryTokens.length === 1 ? 1 : Math.ceil(queryTokens.length * 0.6))) continue;
		const first = tokens.find((token) => matched.some((queryToken) => {
			const maximum = queryToken.length >= 9 ? 2 : queryToken.length >= 5 ? 1 : 0;
			return editDistanceWithin(queryToken, normalize(token[0]), maximum);
		}));
		const start = paragraph.index + (first?.index || 0);
		matches.push({ query, start, end: start + (first?.[0].length || query.length) });
	}
	return matches;
}

export function findPassages(text, queries, mode = "case-insensitive") {
	const terms = Array.isArray(queries) ? queries : [queries];
	const matches = terms.flatMap((query) => {
		if (!query?.trim()) return [];
		if (mode === "fuzzy") return fuzzyMatches(text, query.trim());
		return literalMatches(text, query.trim(), mode === "case-insensitive");
	}).sort((a, b) => a.start - b.start);

	if (matches.length === 0) return { count: 0, output: "No matching passages found." };
	const ranges = [];
	for (const match of matches) {
		const start = Math.max(0, match.start - CONTEXT_CHARS);
		const end = Math.min(text.length, match.end + CONTEXT_CHARS);
		const previous = ranges[ranges.length - 1];
		if (previous && start <= previous.end) {
			previous.end = Math.max(previous.end, end);
			previous.matches.push(match);
		} else {
			ranges.push({ start, end, matches: [match] });
		}
	}

	let output = `Found ${matches.length} match${matches.length === 1 ? "" : "es"}:\n`;
	for (const range of ranges) {
		const passage = text.slice(range.start, range.end);
		const heading = `\n--- chars ${range.start}-${range.end} (${range.matches.map((match) => match.query).join(", ")}) ---\n`;
		if (output.length + heading.length + passage.length > MAX_OUTPUT_CHARS) {
			output += "\n[Output truncated; use a more specific search term.]";
			break;
		}
		output += heading + passage + "\n";
	}
	return { count: matches.length, output };
}
