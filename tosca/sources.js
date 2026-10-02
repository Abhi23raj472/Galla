/* Source adapters. Each one fetches from a public, CORS-enabled API and
   returns questions in one shape:
   { id, source, title, url, author, created, activity, score, answers,
     answered (true/false/null), tags[], excerpt } — dates in ms. */
(function () {
  const TIMEOUT = 12000;

  function decode(html) {
    if (!html) return "";
    const doc = new DOMParser().parseFromString(html, "text/html");
    return (doc.body.textContent || "").replace(/\s+/g, " ").trim();
  }
  function clip(s, n = 240) {
    s = decode(s);
    return s.length > n ? s.slice(0, n).replace(/\s+\S*$/, "") + "…" : s;
  }
  function safeUrl(u) {
    try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : ""; } catch { return ""; }
  }

  class SourceError extends Error {}

  async function getJSON(url) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), TIMEOUT);
    let res;
    try {
      res = await fetch(url, { signal: ctl.signal, headers: { Accept: "application/json" } });
    } catch (e) {
      throw new SourceError(e.name === "AbortError" ? "Timed out" : "Couldn't connect");
    } finally {
      clearTimeout(timer);
    }
    let body = null;
    try { body = await res.json(); } catch { /* non-JSON error page */ }
    if (!res.ok) {
      if (res.status === 429 || res.status === 403) throw new SourceError("Rate limited, try again later");
      throw new SourceError((body && (body.error_message || body.message)) || `HTTP ${res.status}`);
    }
    if (!body) throw new SourceError("Unexpected response");
    return body;
  }

  // Make sure every source is searched for Tosca, not just the user's words.
  function withTosca(q) {
    q = (q || "").trim();
    return /\btosca\b/i.test(q) ? q : ("tosca " + q).trim();
  }
  const enc = encodeURIComponent;

  function stackExchange(site) {
    return async (q) => {
      const url = `https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=activity&q=${enc(withTosca(q))}` +
        `&site=${site}&pagesize=50&filter=withbody`;
      const d = await getJSON(url);
      if (d.error_message) throw new SourceError(d.error_message);
      return (d.items || []).map((it) => ({
        id: `${site}:${it.question_id}`,
        title: decode(it.title),
        url: safeUrl(it.link),
        author: it.owner ? decode(it.owner.display_name) : "",
        created: it.creation_date * 1000,
        activity: (it.last_activity_date || it.creation_date) * 1000,
        score: it.score || 0,
        answers: it.answer_count || 0,
        answered: !!(it.is_answered || it.accepted_answer_id),
        tags: it.tags || [],
        excerpt: clip(it.body),
      }));
    };
  }

  async function reddit(q) {
    const query = `${withTosca(q)} (tricentis OR automation OR testing OR test)`;
    const d = await getJSON(`https://www.reddit.com/search.json?q=${enc(query)}&sort=new&limit=50&type=link&raw_json=1`);
    return ((d.data && d.data.children) || []).map(({ data: p }) => ({
      id: `reddit:${p.id}`,
      title: decode(p.title),
      url: safeUrl("https://www.reddit.com" + p.permalink),
      author: p.author ? "u/" + p.author : "",
      created: p.created_utc * 1000,
      activity: p.created_utc * 1000,
      score: p.score || 0,
      answers: p.num_comments || 0,
      answered: null,
      tags: p.subreddit ? ["r/" + p.subreddit] : [],
      excerpt: clip(p.selftext),
    }));
  }

  async function github(q) {
    const d = await getJSON(`https://api.github.com/search/issues?q=${enc(withTosca(q) + " tricentis is:issue")}&sort=updated&order=desc&per_page=50`);
    return (d.items || []).map((it) => ({
      id: `github:${it.id}`,
      title: decode(it.title),
      url: safeUrl(it.html_url),
      author: it.user ? it.user.login : "",
      created: Date.parse(it.created_at),
      activity: Date.parse(it.updated_at || it.created_at),
      score: (it.reactions && it.reactions.total_count) || 0,
      answers: it.comments || 0,
      answered: it.state === "closed",
      tags: it.repository_url ? [it.repository_url.split("/").slice(-2).join("/")] : [],
      excerpt: clip(it.body),
    }));
  }

  async function hackerNews(q) {
    const d = await getJSON(`https://hn.algolia.com/api/v1/search?query=${enc(withTosca(q) + " tricentis")}&tags=story&hitsPerPage=50`);
    return (d.hits || []).map((h) => ({
      id: `hn:${h.objectID}`,
      title: decode(h.title || h.story_title || ""),
      url: safeUrl(`https://news.ycombinator.com/item?id=${h.objectID}`),
      author: h.author || "",
      created: h.created_at_i * 1000,
      activity: h.created_at_i * 1000,
      score: h.points || 0,
      answers: h.num_comments || 0,
      answered: null,
      tags: [],
      excerpt: clip(h.story_text || ""),
    }));
  }

  // DEV has no full-text search API, so pull the Tosca tags and filter here.
  async function devto(q) {
    const tags = ["tosca", "tricentis"];
    const pages = await Promise.allSettled(tags.map((t) => getJSON(`https://dev.to/api/articles?tag=${t}&per_page=50`)));
    if (pages.every((p) => p.status === "rejected")) throw pages[0].reason;
    const words = (q || "").toLowerCase().split(/\s+/).filter((w) => w && w !== "tosca");
    const seen = new Set(), out = [];
    for (const p of pages) {
      if (p.status !== "fulfilled" || !Array.isArray(p.value)) continue;
      for (const a of p.value) {
        if (seen.has(a.id)) continue;
        seen.add(a.id);
        const hay = `${a.title} ${a.description} ${(a.tag_list || []).join(" ")}`.toLowerCase();
        if (words.length && !words.every((w) => hay.includes(w))) continue;
        out.push({
          id: `devto:${a.id}`,
          title: decode(a.title),
          url: safeUrl(a.url),
          author: a.user ? a.user.name || a.user.username : "",
          created: Date.parse(a.published_at),
          activity: Date.parse(a.edited_at || a.published_at),
          score: a.public_reactions_count || 0,
          answers: a.comments_count || 0,
          answered: null,
          tags: Array.isArray(a.tag_list) ? a.tag_list : [],
          excerpt: clip(a.description),
        });
      }
    }
    return out;
  }

  window.TQH_SOURCES = [
    { id: "stackoverflow", name: "Stack Overflow", color: "var(--c-so)", fetch: stackExchange("stackoverflow") },
    { id: "sqa", name: "SQA Stack Exchange", color: "var(--c-sqa)", fetch: stackExchange("sqa") },
    { id: "reddit", name: "Reddit", color: "var(--c-reddit)", fetch: reddit },
    { id: "github", name: "GitHub issues", color: "var(--c-github)", fetch: github },
    { id: "hn", name: "Hacker News", color: "var(--c-hn)", fetch: hackerNews },
    { id: "devto", name: "DEV", color: "var(--c-devto)", fetch: devto },
  ];

  // Sites with no open API: offered as search links instead.
  window.TQH_ELSEWHERE = [
    { name: "Tricentis docs", url: (q) => `https://duckduckgo.com/?q=${enc("site:documentation.tricentis.com " + q)}` },
    { name: "Tricentis Community", url: (q) => `https://duckduckgo.com/?q=${enc("tricentis community " + withTosca(q))}` },
    { name: "Tricentis Academy", url: (q) => `https://duckduckgo.com/?q=${enc("tricentis academy " + withTosca(q))}` },
    { name: "YouTube", url: (q) => `https://www.youtube.com/results?search_query=${enc(withTosca(q) + " tricentis")}` },
    { name: "LinkedIn posts", url: (q) => `https://www.linkedin.com/search/results/content/?keywords=${enc(withTosca(q))}` },
    { name: "Quora", url: (q) => `https://www.quora.com/search?q=${enc(withTosca(q))}` },
  ];

  window.TQH_UTIL = { withTosca, decode };
})();
