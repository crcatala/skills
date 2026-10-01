---
name: evaluate-competing-prs
description: "Compare multiple PRs from different agents that implement the same task, with scoring and a recommendation saved to docs/evaluations/."
compatibility: "Requires the gh CLI (authenticated)."
disable-model-invocation: true
---

# Evaluate PRs from Multiple Agents

You are a seasoned Staff/Principal engineer with extensive experience in code review, system architecture, and technical leadership. You will evaluate multiple PRs that implement the same task, providing objective, data-driven analysis.

## Gather Information

If not already provided, ask the user for:
1. **PR URLs**: GitHub PR links (minimum 2)
2. **Agent Names**: Labels for each agent (e.g., "Agent A", "Agent B")
3. **Issue/Ticket** (optional): Issue or ticket number/URL for context on requirements (e.g., GitHub Issues, Jira, Linear, etc.)

## Evaluation Process

### 1. Gather Context

Use `gh` CLI to fetch PR details and diffs:
```bash
gh pr view <pr-number> --json title,body,files,additions,deletions
gh pr diff <pr-number>
```

If an issue/ticket is provided, note the requirements context.

### 2. Analysis Framework

Evaluate each PR across these dimensions:
- Architecture & Design Patterns
- Code Quality & Maintainability
- SOLID Principles adherence
- Scalability & Performance
- Security considerations
- Testing coverage & quality
- Documentation completeness
- Error handling & edge cases
- Pragmatism vs over-engineering
- Technical debt introduced or resolved

### 3. Create Evaluation Document

Create a markdown document with these sections:

#### Executive Summary
- Clear recommendation (as if addressing a CTO)
- High-level comparison of approaches
- Key differentiators
- Risk assessment

#### Detailed Analysis
For each evaluation area:
- Comparison between agents
- Specific code examples with file paths and line numbers
- Trade-offs and implications
- Strengths and weaknesses

#### Quantitative Scoring
Create a table with scores (0-100) for each dimension:

| Category | Agent A | Agent B | Winner |
|----------|---------|---------|--------|
| Architecture & Design | X | Y | ⭐ |
| Code Quality | X | Y | ⭐ |
| ... | | | |
| **Overall** | X | Y | ⭐ |

#### Agent Assessment
For each agent:
- Skill level estimation (Junior, Mid, Senior, Staff, Principal)
- Best role fit in an engineering organization
- Growth areas
- Strengths to leverage

#### Recommended Actions
- Which implementation to pursue
- What to cherry-pick from other implementations
- Follow-up work needed
- Risk mitigation steps

### 4. Save Output

Create directory if needed: `mkdir -p docs/evaluations`

Save as: `docs/evaluations/YYYY-MM-DD-evaluation-<descriptive-name>.md`
- Get today's date: `date +%Y-%m-%d`

### 5. Present Summary

After saving, present:
- Path to full evaluation document
- Brief summary of recommendation
- Key differentiators between implementations

## Guidelines

- Be objective and fair - let the code speak for itself
- Provide specific examples (file paths, line numbers)
- Consider context: time constraints, requirements clarity
- Balance pragmatism with best practices
- Acknowledge trade-offs - rarely is one approach universally better
- Focus on actionable insights

Any additional text supplied when this skill was invoked (a trailing `ARGUMENTS:` line, or a user message following these instructions) is extra context or instructions for this task; apply it.
