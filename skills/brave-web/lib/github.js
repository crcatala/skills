import { execFileSync } from "node:child_process";

const NON_REPOSITORY_PATHS = new Set(["issues", "pull", "pulls", "discussions", "releases", "wiki", "actions", "settings", "security", "projects", "graphs", "compare", "commits", "tags", "branches", "stargazers", "watchers", "network", "forks"]);

export function parseGitHubUrl(urlString) {
	let url;
	try { url = new URL(urlString); } catch { return null; }
	if (!["github.com", "www.github.com"].includes(url.hostname.toLowerCase())) return null;
	const parts = url.pathname.split("/").filter(Boolean).map((part) => decodeURIComponent(part));
	if (parts.length < 2 || NON_REPOSITORY_PATHS.has(parts[2]?.toLowerCase())) return null;
	const [owner, repoWithExtension, view, ref, ...path] = parts;
	const repo = repoWithExtension.replace(/\.git$/, "");
	if (!/^[\w.-]+$/.test(owner) || !/^[\w.-]+$/.test(repo)) return null;
	return { owner, repo, view, ref, path };
}

export function githubGuidance(urlString) {
	const parsed = parseGitHubUrl(urlString);
	if (!parsed) return null;
	const slug = `${parsed.owner}/${parsed.repo}`;
	const quotedUrl = JSON.stringify(urlString);
	let detail;
	if (parsed.view === "blob") {
		detail = "Use `gh api` for the raw file; branch names can contain slashes, so preserve the URL when resolving its ref and path.";
	} else if (parsed.view === "tree") {
		detail = "Use `gh api repos/OWNER/REPO/contents/PATH` or a shallow clone to inspect this directory.";
	} else {
		detail = "Use `gh repo view` for the README/metadata or a shallow clone to explore files.";
	}
	return [
		"# GitHub URL detected",
		"",
		"GitHub content is intentionally not scraped as rendered HTML.",
		detail,
		"",
		"```bash",
		`gh repo view ${slug}`,
		`gh api repos/${slug}/readme -H "Accept: application/vnd.github.raw"`,
		`git clone --depth 1 https://github.com/${slug}.git`,
		"```",
		"",
		`Original URL: ${quotedUrl}`,
	].join("\n");
}

export function fetchGitHubRepoOverview(urlString, execFile = execFileSync) {
	const parsed = parseGitHubUrl(urlString);
	if (!parsed || parsed.view) return null;
	const slug = `${parsed.owner}/${parsed.repo}`;
	try {
		const output = execFile("gh", ["repo", "view", slug, "--json", "nameWithOwner,description,url,defaultBranchRef"], { encoding: "utf8", timeout: 15000 });
		return `# ${slug}\n\n${output.trim()}`;
	} catch {
		return githubGuidance(urlString);
	}
}
