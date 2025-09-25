# crypto_feed_pipeline.py
import feedparser, requests, hashlib, time
from feedgen.feed import FeedGenerator
from newspaper import Article
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
import datetime
import os

# === CONFIG ===
RSS_SOURCES = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/", 
    "https://cryptobriefing.com/feed/",
    "https://decrypt.co/feed",
    "https://www.theblock.co/feed",
    "https://coinsbench.com/feed",  # add/remove as needed
    # producthunt RSS for crypto tag (example)
    "https://www.producthunt.com/feed/tag/crypto",
]
OUTPUT_RSS = "combined_crypto_companies.xml"
MAX_ARTICLE_WORDS = 400

# Optional LLM config (pseudo)
USE_LLM_SUMMARY = False
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# === HELPERS ===
def fingerprint(item):
    base = (item.get('link') or "") + (item.get('title') or "")
    return hashlib.sha256(base.encode('utf-8')).hexdigest()

def fetch_article_text(url):
    try:
        art = Article(url)
        art.download()
        art.parse()
        text = art.text
        if not text:
            # fallback to simple HTML text
            r = requests.get(url, timeout=8)
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(separator="\n")
        return text[:MAX_ARTICLE_WORDS]
    except Exception as e:
        return ""

def summarize_with_llm(title, excerpt, url):
    # Placeholder: you can plug in an LLM call here
    # Example: call OpenAI to create a 2-line summary & tags
    if not USE_LLM_SUMMARY:
        return {"summary": excerpt[:300], "tags": []}
    import openai
    openai.api_key = OPENAI_API_KEY
    prompt = f"Summarize in 2 short sentences and give up to 4 tags. Title: {title}\n\nExcerpt:\n{excerpt}\n\nReturn JSON with keys: summary, tags (list)."
    resp = openai.Completion.create(
        engine="gpt-4o-mini", prompt=prompt, max_tokens=150, temperature=0.2
    )
    text = resp.choices[0].text.strip()
    # naive parse: real code should parse JSON safely
    return {"summary": text, "tags": []}
# === MAIN ===
def main():
    seen = set()
    items = []

    for src in RSS_SOURCES:
        try:
            d = feedparser.parse(src)
            for entry in d.entries:
                fp = fingerprint(entry)
                if fp in seen:
                    continue
                seen.add(fp)

                title = entry.get('title', '')
                link = entry.get('link', '')
                published = entry.get('published', entry.get('updated', ''))
                try:
                    published_parsed = dateparser.parse(published).isoformat()
                except:
                    published_parsed = datetime.datetime.utcnow().isoformat()

                excerpt = entry.get('summary', '') or entry.get('description', '')
                # Optionally fetch full article for richer summary
                article_text = fetch_article_text(link) if link else excerpt

                # LLM summarize (optional)
                summary_obj = summarize_with_llm(title, article_text or excerpt, link)

                items.append({
                    "title": title,
                    "link": link,
                    "published": published_parsed,
                    "summary": summary_obj.get("summary"),
                    "source": src
                })
        except Exception as e:
            print("Error fetching", src, e)

    # sort by published
    items.sort(key=lambda x: x["published"], reverse=True)

    # create combined RSS
    fg = FeedGenerator()
    fg.title("Crypto Companies — Combined Feed")
    fg.link(href="https://example.local/combined", rel="self")
    fg.description("Aggregated feed of new/upcoming crypto companies, launches, and funding")
    fg.language("en")

    for it in items:
       fe = fg.add_entry()
        fe.title(it["title"])
        fe.link(href=it["link"])
        fe.pubDate(it["published"])
        content = f"{it['summary']}\n\nSource: {it['source']}"
        fe.description(content)

    fg.rss_file(OUTPUT_RSS)
    print("Wrote", OUTPUT_RSS)

if __name__ == "__main__":
    main()
