#!/usr/bin/env node

const args = process.argv.slice(2);

// Parse --json flag
const jsonIndex = args.indexOf("--json");
const outputJson = jsonIndex !== -1;
if (outputJson) args.splice(jsonIndex, 1);

// Parse --tokens option
let tokensNum = 5000;
const tokensIndex = args.indexOf("--tokens");
if (tokensIndex !== -1 && args[tokensIndex + 1]) {
	tokensNum = parseInt(args[tokensIndex + 1], 10);
	args.splice(tokensIndex, 2);
}

const query = args.join(" ");

if (!query) {
	console.log("Usage: code.js <query> [options]");
	console.log("\nSearch for code documentation, examples, and API references using Exa AI.");
	console.log("Optimized for programming-related queries with high-quality, up-to-date results.");
	console.log("\nOptions:");
	console.log("  --tokens <num>      Token budget for response (default: 5000, range: 1000-50000)");
	console.log("  --json              Output raw JSON instead of formatted text");
	console.log("\nEnvironment:");
	console.log("  EXA_API_KEY         Required. Your Exa API key.");
	console.log("\nToken Guidelines:");
	console.log("  1000-2000           Quick focused answer");
	console.log("  3000-5000           Standard documentation lookup");
	console.log("  8000-15000          Comprehensive examples");
	console.log("  20000-50000         Deep dive / multiple concepts");
	console.log("\nExamples:");
	console.log('  code.js "React useState hook examples"');
	console.log('  code.js "Python pandas dataframe filtering" --tokens 8000');
	console.log('  code.js "Express.js middleware authentication"');
	console.log('  code.js "Go error handling best practices" --tokens 10000');
	console.log('  code.js "Next.js app router server components"');
	process.exit(1);
}

const apiKey = process.env.EXA_API_KEY;
if (!apiKey) {
	console.error("Error: EXA_API_KEY environment variable is required.");
	console.error("Get your API key at: https://exa.ai");
	process.exit(1);
}

// Clamp tokens to valid range
tokensNum = Math.max(1000, Math.min(50000, tokensNum));

async function searchCode() {
	const response = await fetch("https://api.exa.ai/context", {
		method: "POST",
		headers: {
			"accept": "application/json",
			"content-type": "application/json",
			"x-api-key": apiKey,
		},
		body: JSON.stringify({
			query,
			tokensNum,
		}),
	});

	if (!response.ok) {
		const errorText = await response.text();
		throw new Error(`HTTP ${response.status}: ${response.statusText}\n${errorText}`);
	}

	return response.json();
}

try {
	const data = await searchCode();

	if (outputJson) {
		console.log(JSON.stringify(data, null, 2));
		process.exit(0);
	}

	if (!data.response) {
		console.log("No results found. Try a different query or be more specific about the library/framework.");
		process.exit(0);
	}

	// Output header with metadata
	console.log(`# Code Context: ${query}`);
	console.log("");
	if (data.resultsCount) {
		console.log(`Sources: ${data.resultsCount} results`);
	}
	if (data.searchTime) {
		console.log(`Search time: ${data.searchTime.toFixed(2)}s`);
	}
	console.log("");
	console.log("---");
	console.log("");

	// Output the response content
	console.log(data.response);
} catch (e) {
	console.error(`Error: ${e.message}`);
	process.exit(1);
}
