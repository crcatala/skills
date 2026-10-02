# Third-party notices

## brave-web

`skills/brave-web` is derived from the `brave-search` skill in
[badlogic/pi-skills](https://github.com/badlogic/pi-skills), which is
distributed under the following license. It has since been extended
(content extraction, caching, SSRF guards, domain filters, tests).
The same notice is bundled in
[skills/brave-web/THIRD_PARTY_NOTICE.md](skills/brave-web/THIRD_PARTY_NOTICE.md)
so attribution travels with standalone copies.

```
MIT License

Copyright (c) 2024 Mario Zechner

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## agent-browser

The thin browser QA policy consults guides supplied by the installed
[Vercel agent-browser CLI](https://github.com/vercel-labs/agent-browser) rather
than bundling an upstream command catalog. Apache-2.0 attribution from the
earlier guide is retained in
[the skill's notice](skills/agent-browser/THIRD_PARTY_NOTICE.md) and
[bundled upstream license](skills/agent-browser/LICENSE). These files must travel
with standalone copies; the root MIT license does not replace upstream terms.
Fetched official guides remain subject to their upstream license.

## ticket

The command reference draws on MIT-licensed
[wedow/ticket](https://github.com/wedow/ticket). Its upstream copyright/permission
notice, including the unchanged copyright line at the installation pin, is
bundled in [skills/ticket/THIRD_PARTY_NOTICE.md](skills/ticket/THIRD_PARTY_NOTICE.md).

## sentry

The skill supplies this repository's read-only investigation policy. Command
syntax is delegated to installed CLI help and official documentation rather
than bundling Sentry's CLI implementation, command catalog, or official agent skill.

The external [Sentry CLI](https://github.com/getsentry/cli) is separately licensed
under [FSL-1.1-Apache-2.0](https://github.com/getsentry/cli/blob/main/LICENSE.md).
Its software and documentation are not relicensed by this repository. Users
fetching official documentation or installing the CLI must follow the applicable
upstream terms. Sentry is a third-party product; this skill is not an official
Sentry distribution.

## terminal-capture

The skill builds and runs external tools but does not bundle or relicense them.
[svgcast](https://github.com/co2water/svgcast) (Apache-2.0) is compiled from
source at a pinned version on the user's machine, as is
[Betterleaks](https://github.com/betterleaks/betterleaks) (MIT), used as a second
secret-scanning engine. [VHS](https://github.com/charmbracelet/vhs)
(MIT), the fallback for PNG/GIF/video output, is installed separately by the user.
The recorder, secret scanner, and preview helper in the skill are original to this
repository.
