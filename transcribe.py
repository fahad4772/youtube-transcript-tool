import json
import os
import re
import smtplib
import unicodedata
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from email.message import EmailMessage
from urllib.parse import parse_qs, urlparse
from uuid import uuid4
from xml.etree.ElementTree import ParseError

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.utils import secure_filename
from youtube_transcript_api import YouTubeTranscriptApi

try:
    from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
except ImportError:
    from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"
CONTENT_FILE = BASE_DIR / "site_content.json"
CONTACT_FILE = BASE_DIR / "contact_messages.json"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
)
app.secret_key = os.environ.get("U2BTOOLS_SECRET_KEY", "u2btools-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
api = YouTubeTranscriptApi()

PRIMARY_NAV = [
    {"label": "Tool", "endpoint": "index"},
    {"label": "Blog", "endpoint": "blog_index"},
    {"label": "About", "endpoint": "about"},
    {"label": "Contact", "endpoint": "contact"},
]

LEGAL_LINKS = [
    {"label": "Privacy Policy", "endpoint": "privacy"},
    {"label": "Terms & Conditions", "endpoint": "terms"},
    {"label": "Disclaimer", "endpoint": "disclaimer"},
    {"label": "Editorial Guidelines", "endpoint": "editorial"},
]

RESOURCE_LINKS = [
    {"label": "Home", "endpoint": "index"},
    {"label": "Blog", "endpoint": "blog_index"},
    {"label": "About Us", "endpoint": "about"},
    {"label": "Contact Us", "endpoint": "contact"},
]

EDITOR_SLUG = os.environ.get("U2BTOOLS_EDITOR_SLUG", "u2btools-studio-847291")
EDITOR_PASSWORD = os.environ.get("U2BTOOLS_EDITOR_PASSWORD", "U2btools@2026")
EDITOR_SESSION_KEY = "u2btools_editor_auth"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

DEFAULT_CONTENT = {
    "site": {
        "name": "U2btools",
        "tagline": "Fast YouTube transcript tools and practical video content guides.",
        "email": "hello@u2btools.com",
        "domain": "https://u2btools.com",
        "year": date.today().year,
    },
    "home": {
        "hero_badge": "Instant Transcript Tool",
        "hero_title": "Turn YouTube videos into clear text without wasting time.",
        "hero_subtitle": "Paste a YouTube link, grab the transcript, and then build notes, blog drafts, summaries, or research from one clean workflow.",
        "hero_note": "This homepage is designed so the main input appears immediately when the page loads.",
        "tool_heading": "Paste a YouTube URL and get the transcript",
        "tool_description": "Supports watch links, short links, shorts URLs, and embed URLs.",
        "home_article_title": "",
        "home_article_body_html": (
            "<p>Good transcript tools help people move faster. Instead of replaying the same part of a video again and again, "
            "users can scan the text, copy important parts, and turn spoken ideas into something usable.</p>"
            "<p>That matters for students taking notes, marketers building content briefs, writers turning video into articles, "
            "and business teams documenting meetings or tutorials.</p>"
            "<p>On a strong site, the tool should live alongside helpful articles, internal links, policy pages, and clear contact details. "
            "That gives visitors more confidence and gives the website more depth than a single isolated form.</p>"
        ),
        "feature_cards": [
            {"title": "Fast start", "text": "The transcript input is visible above the fold so users can start immediately."},
            {"title": "Useful output", "text": "Copy the transcript for article drafts, notes, briefs, captions, and research."},
            {"title": "Content hub", "text": "The homepage links into blog articles so the site feels more complete and useful."},
        ],
        "audience_pills": ["Students and notes", "SEO and article outlines", "Creators and repurposing"],
        "faq": [
            {"question": "Is the tool free to use?", "answer": "Yes. You can paste a supported YouTube URL and retrieve transcript text when captions are available."},
            {"question": "Why does a transcript fail sometimes?", "answer": "Common reasons include missing captions, disabled transcripts, private videos, regional restrictions, or temporary source issues."},
            {"question": "Can I use transcripts for article writing?", "answer": "Yes. Many users turn transcript text into notes, article outlines, FAQs, summaries, and briefing documents."},
            {"question": "Can I change this homepage later?", "answer": "Yes. The editor page lets you update hero text, homepage content, and blog posts without editing Python code."},
        ],
    },
    "blog_posts": [
        {
            "slug": "how-to-get-a-youtube-transcript",
            "title": "How to Get a YouTube Transcript Quickly and Cleanly",
            "description": "A practical guide to extracting captions, cleaning filler text, and turning transcripts into notes.",
            "category": "Guides",
            "read_time": "6 min read",
            "published": "2026-03-31",
            "image": "https://images.unsplash.com/photo-1499750310107-5fef28a66643?auto=format&fit=crop&w=1200&q=80",
            "intro": "YouTube transcripts help with research, note-taking, content repurposing, and accessibility.",
            "body_html": "<h2>Why transcripts are useful</h2><p>Transcripts make long-form video easier to search, quote, summarize, and repurpose.</p><p>If you regularly work with video content, you may also want to read our internal guide on <a href='/blog/video-to-blog-workflow'>turning video into blog posts</a>.</p><h2>When a transcript may not load</h2><p>Some videos do not have captions, and some publishers disable transcript access.</p><p>For general caption policy context, YouTube provides public help documentation at <a href='https://support.google.com/youtube/answer/6373554?hl=en' target='_blank' rel='noopener'>YouTube Help</a>.</p>",
        },
        {
            "slug": "video-to-blog-workflow",
            "title": "Turn a Video Transcript into a Blog Post Workflow",
            "description": "Use transcript text to produce articles, FAQs, summaries, and supporting pages for organic traffic.",
            "category": "SEO",
            "read_time": "7 min read",
            "published": "2026-03-31",
            "image": "https://images.unsplash.com/photo-1455390582262-044cdead277a?auto=format&fit=crop&w=1200&q=80",
            "intro": "A raw transcript is rarely publish-ready, but it is a strong starting point for articles, tutorials, and FAQs.",
            "body_html": "<h2>Start with structure</h2><p>Break the transcript into major ideas first, then build a headline, summary, and action steps.</p><p>For site owners, this usually works best when paired with policy pages, contact information, and a real publishing section.</p><h2>Create supporting pages</h2><p>Strong sites usually include pages for About, Contact, Privacy Policy, Terms, and editorial standards.</p><p>You can also link out to reputable references when useful, such as <a href='https://developers.google.com/search/docs/fundamentals/creating-helpful-content' target='_blank' rel='noopener'>Google Search guidance on helpful content</a>.</p>",
        },
        {
            "slug": "best-ways-to-use-youtube-transcripts",
            "title": "Best Ways to Use YouTube Transcripts for Research and Content",
            "description": "Practical transcript use cases for study notes, content briefs, article outlines, and team documentation.",
            "category": "Ideas",
            "read_time": "5 min read",
            "published": "2026-03-31",
            "image": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80",
            "intro": "Once you have the transcript, the real value comes from what you do next.",
            "body_html": "<h2>Research and note-taking</h2><p>Students and researchers often use transcripts to skim lectures or interviews before deciding what to watch in full.</p><h2>Accessibility and clarity</h2><p>Transcript access helps users read at their own pace and can make content easier to understand.</p><p>For broader accessibility standards, the <a href='https://www.w3.org/WAI/' target='_blank' rel='noopener'>W3C Web Accessibility Initiative</a> offers helpful guidance.</p>",
        },
    ],
    "pages": {
        "about": {
            "title": "About U2btools",
            "description": "Learn what U2btools does, who it serves, and how the site approaches transcript-based tools and educational content.",
            "hero": "A publishing-style site built around useful transcript tools and practical video workflows.",
            "body_html": "<h2>What we do</h2><p>U2btools helps people pull YouTube transcripts and turn them into something usable: notes, outlines, summaries, blog drafts, and research material.</p><h2>Who this site is for</h2><p>This site is built for students, researchers, creators, SEO teams, writers, and anyone who needs quick access to spoken content in text form.</p>",
        },
        "contact": {
            "title": "Contact Us",
            "description": "Contact U2btools for support, feedback, business questions, or content corrections.",
            "hero": "Questions, corrections, partnerships, or general feedback are welcome.",
            "body_html": "<h2>How to reach us</h2><p>Email us for support, corrections, or business enquiries.</p><p>When reporting a bug, include the YouTube URL you tested and the exact message shown on the page.</p>",
        },
        "privacy": {
            "title": "Privacy Policy",
            "description": "Read how U2btools handles basic website information, contact messages, and third-party services.",
            "hero": "A straightforward overview of the information this site may handle.",
            "body_html": "<h2>Information we may receive</h2><p>If you contact us directly, we may receive the information you choose to send, such as your name, email address, and message details.</p><p>The transcript tool processes the YouTube URL you submit in order to request transcript data from the relevant source.</p><h2>Third-party services</h2><p>This site may use third-party services for hosting, analytics, fonts, and embedded content.</p>",
        },
        "terms": {
            "title": "Terms & Conditions",
            "description": "Read the basic terms for using U2btools and its educational content.",
            "hero": "Simple terms for using the tool and reading the site.",
            "body_html": "<h2>Use of the website</h2><p>You agree to use this website lawfully and not to misuse the service or submit content you do not have the right to use.</p><p>The tool is provided as-is without guaranteed availability, accuracy, or suitability for a specific purpose.</p>",
        },
        "disclaimer": {
            "title": "Disclaimer",
            "description": "Understand the general limitations of the tool, article content, and third-party references on U2btools.",
            "hero": "Helpful information, but no absolute guarantees.",
            "body_html": "<h2>General content disclaimer</h2><p>The material on this site is published for general information and usability guidance.</p><p>External links are included for reference and convenience. We do not control third-party sites or guarantee their content.</p>",
        },
        "editorial": {
            "title": "Editorial Guidelines",
            "description": "Learn how U2btools approaches tutorial content, corrections, references, and updates.",
            "hero": "A small but clear editorial standard for practical web content.",
            "body_html": "<h2>How articles are written</h2><p>Articles are written to be practical, readable, and task-focused.</p><p>If you spot an error or outdated claim, email us with the page URL and correction details.</p>",
        },
    },
}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    return cleaned or "section"


def allowed_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_IMAGE_EXTENSIONS


def load_content():
    if CONTENT_FILE.exists():
        try:
            with CONTENT_FILE.open("r", encoding="utf-8") as file:
                content = json.load(file)
                if {"site", "home", "blog_posts", "pages"}.issubset(content.keys()):
                    return content
        except (OSError, json.JSONDecodeError):
            pass
    content = deepcopy(DEFAULT_CONTENT)
    env_email = os.environ.get("U2BTOOLS_SITE_EMAIL", "").strip()
    env_domain = os.environ.get("U2BTOOLS_SITE_DOMAIN", "").strip()
    if env_email:
        content["site"]["email"] = env_email
    if env_domain:
        content["site"]["domain"] = env_domain
    save_content(content)
    return content


def save_content(content):
    with CONTENT_FILE.open("w", encoding="utf-8") as file:
        json.dump(content, file, indent=2, ensure_ascii=False)


def load_contact_messages():
    if CONTACT_FILE.exists():
        try:
            with CONTACT_FILE.open("r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
        except (OSError, json.JSONDecodeError):
            pass
    return []


def save_contact_messages(messages):
    with CONTACT_FILE.open("w", encoding="utf-8") as file:
        json.dump(messages, file, indent=2, ensure_ascii=False)


def extract_video_id(video_url: str) -> str | None:
    if not video_url:
        return None
    parsed = urlparse(video_url.strip())
    host = parsed.netloc.lower()
    if host in {"youtu.be", "www.youtu.be"}:
        return parsed.path.lstrip("/") or None
    if host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            parts = [part for part in parsed.path.split("/") if part]
            return parts[-1] if parts else None
    return None


def transcript_to_text(transcript_data) -> str:
    lines = []
    for item in transcript_data:
        if hasattr(item, "text"):
            lines.append(item.text)
        elif isinstance(item, dict):
            lines.append(item.get("text", ""))
    return "\n".join(line for line in lines if line)


def get_blog_post(posts, slug: str):
    for post in posts:
        if post["slug"] == slug:
            return post
    return None


def editor_authenticated() -> bool:
    return bool(session.get(EDITOR_SESSION_KEY))


def require_editor_auth():
    if not editor_authenticated():
        abort(404)


def save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        raise ValueError("No image file received.")
    if not allowed_image(file_storage.filename):
        raise ValueError("Unsupported image type. Use JPG, PNG, WEBP, or GIF.")
    safe_name = secure_filename(file_storage.filename)
    suffix = Path(safe_name).suffix.lower()
    stored_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}{suffix}"
    target = UPLOADS_DIR / stored_name
    file_storage.save(target)
    return url_for("static", filename=f"uploads/{stored_name}")


def send_contact_email(name: str, email: str, subject: str, message_text: str) -> bool:
    smtp_host = os.environ.get("U2BTOOLS_SMTP_HOST", "").strip()
    smtp_port = int(os.environ.get("U2BTOOLS_SMTP_PORT", "587"))
    smtp_user = os.environ.get("U2BTOOLS_SMTP_USER", "").strip()
    smtp_password = os.environ.get("U2BTOOLS_SMTP_PASSWORD", "").strip()
    smtp_to = os.environ.get("U2BTOOLS_CONTACT_TO", "").strip() or os.environ.get("U2BTOOLS_SMTP_USER", "").strip()
    smtp_from = os.environ.get("U2BTOOLS_CONTACT_FROM", "").strip() or smtp_user

    if not all([smtp_host, smtp_user, smtp_password, smtp_to, smtp_from]):
        return False

    msg = EmailMessage()
    msg["Subject"] = f"Website contact: {subject}"
    msg["From"] = smtp_from
    msg["To"] = smtp_to
    msg["Reply-To"] = email
    msg.set_content(
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Subject: {subject}\n\n"
        f"{message_text}"
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
    return True


def add_heading_ids(html_text: str):
    headings = []
    seen = {}

    def replace_heading(match):
        level = match.group(1)
        attrs = match.group(2) or ""
        title = re.sub(r"<[^>]+>", "", match.group(3)).strip()
        base_id = slugify(title)
        count = seen.get(base_id, 0)
        seen[base_id] = count + 1
        heading_id = base_id if count == 0 else f"{base_id}-{count + 1}"
        headings.append({"id": heading_id, "title": title, "level": int(level)})
        cleaned_attrs = re.sub(r'\s+id="[^"]*"', "", attrs)
        return f'<h{level}{cleaned_attrs} id="{heading_id}">{match.group(3)}</h{level}>'

    updated = re.sub(r"<h([2-3])([^>]*)>(.*?)</h\1>", replace_heading, html_text, flags=re.IGNORECASE | re.DOTALL)
    return updated, headings


def article_schema(post, canonical_url, image_url):
    return {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "description": post["description"],
        "datePublished": post["published"],
        "dateModified": post["published"],
        "author": {"@type": "Organization", "name": "U2btools Editorial Team"},
        "publisher": {"@type": "Organization", "name": "U2btools"},
        "mainEntityOfPage": canonical_url,
        "image": [image_url] if image_url else [],
    }


def page_schema(title, description, canonical_url):
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "description": description,
        "url": canonical_url,
    }


@app.context_processor
def inject_globals():
    content = load_content()
    return {
        "site": content["site"],
        "primary_nav": PRIMARY_NAV,
        "legal_links": LEGAL_LINKS,
        "resource_links": RESOURCE_LINKS,
        "editor_authenticated": editor_authenticated(),
    }


@app.route("/", methods=["GET", "POST"])
def index():
    content = load_content()
    transcript_text = ""
    error = ""
    lang_name = ""
    video_id = ""

    if request.method == "POST":
        video_url = request.form.get("video_url", "")
        video_id = extract_video_id(video_url) or ""
        if not video_id:
            error = "Invalid YouTube URL format."
        else:
            try:
                transcript_list = api.list(video_id)
                language_codes = [transcript.language_code for transcript in transcript_list]
                try:
                    transcript = transcript_list.find_manually_created_transcript(language_codes)
                except NoTranscriptFound:
                    transcript = transcript_list.find_generated_transcript(language_codes)
                transcript_data = transcript.fetch()
                transcript_text = transcript_to_text(transcript_data)
                lang_name = transcript.language
            except TranscriptsDisabled:
                error = "Transcripts are disabled for this video."
            except NoTranscriptFound:
                error = "No transcript was found for this video."
            except ParseError:
                error = "Could not read transcript data from YouTube. Try another public video with captions enabled."
            except Exception as exc:
                error = f"Error: {exc}"

    canonical_url = url_for("index", _external=True)
    schema = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": f"{content['site']['name']} YouTube Transcript Tool",
        "applicationCategory": "UtilityApplication",
        "description": "Extract YouTube transcripts, copy the text, and reuse it for notes, outlines, and content production.",
        "url": canonical_url,
    }
    return render_template(
        "tool.html",
        transcript=transcript_text,
        error=error,
        lang_name=lang_name,
        video_id=video_id,
        home=content["home"],
        featured_posts=content["blog_posts"][:3],
        meta_title=f"{content['site']['name']} | Free YouTube Transcript Tool, Guides, and Blog",
        meta_description="Extract YouTube transcripts, read practical tutorials, and explore SEO-friendly guides for turning video content into useful text.",
        canonical_url=canonical_url,
        meta_image=content["blog_posts"][0].get("image", ""),
        schema_json_ld=[schema],
    )


@app.route(f"/{EDITOR_SLUG}", methods=["GET", "POST"])
def editor():
    content = load_content()
    login_error = ""
    message = ""

    if not editor_authenticated():
        if request.method == "POST":
            password = request.form.get("editor_password", "")
            if password == EDITOR_PASSWORD:
                session[EDITOR_SESSION_KEY] = True
                return redirect(url_for("editor"))
            login_error = "Incorrect password."
        return render_template(
            "editor_login.html",
            login_error=login_error,
            meta_title=f"{content['site']['name']} Admin Login",
            meta_description="Private editor login.",
            canonical_url=url_for("editor", _external=True),
        )

    if request.method == "POST":
        site = content["site"]
        home = content["home"]
        site["name"] = request.form.get("site_name", site["name"]).strip() or site["name"]
        site["tagline"] = request.form.get("site_tagline", site["tagline"]).strip()
        site["email"] = request.form.get("site_email", site["email"]).strip()
        site["domain"] = request.form.get("site_domain", site["domain"]).strip()
        home["hero_badge"] = request.form.get("hero_badge", home["hero_badge"]).strip()
        home["hero_title"] = request.form.get("hero_title", home["hero_title"]).strip()
        home["hero_subtitle"] = request.form.get("hero_subtitle", home["hero_subtitle"]).strip()
        home["hero_note"] = request.form.get("hero_note", home["hero_note"]).strip()
        home["tool_heading"] = request.form.get("tool_heading", home["tool_heading"]).strip()
        home["tool_description"] = request.form.get("tool_description", home["tool_description"]).strip()
        home["home_article_title"] = request.form.get("home_article_title", home["home_article_title"]).strip()
        home["home_article_body_html"] = request.form.get("home_article_body_html", home["home_article_body_html"]).strip()

        pill_slots = max(len(home["audience_pills"]), 3)
        if any(f"audience_pill_{index}" in request.form for index in range(pill_slots)):
            home["audience_pills"] = []
            for index in range(pill_slots):
                pill = request.form.get(f"audience_pill_{index}", "").strip()
                if pill:
                    home["audience_pills"].append(pill)

        feature_slots = max(len(home["feature_cards"]), 3)
        if any(f"feature_title_{index}" in request.form or f"feature_text_{index}" in request.form for index in range(feature_slots)):
            home["feature_cards"] = []
            for index in range(feature_slots):
                title = request.form.get(f"feature_title_{index}", "").strip()
                text = request.form.get(f"feature_text_{index}", "").strip()
                if title or text:
                    home["feature_cards"].append({"title": title, "text": text})

        faq_slots = max(len(home["faq"]), 4)
        if any(f"faq_question_{index}" in request.form or f"faq_answer_{index}" in request.form for index in range(faq_slots)):
            home["faq"] = []
            for index in range(faq_slots):
                question = request.form.get(f"faq_question_{index}", "").strip()
                answer = request.form.get(f"faq_answer_{index}", "").strip()
                if question or answer:
                    home["faq"].append({"question": question, "answer": answer})

        for index, post in enumerate(content["blog_posts"]):
            post["slug"] = request.form.get(f"post_slug_{index}", post["slug"]).strip() or post["slug"]
            post["title"] = request.form.get(f"post_title_{index}", post["title"]).strip()
            post["category"] = request.form.get(f"post_category_{index}", post["category"]).strip()
            post["read_time"] = request.form.get(f"post_read_time_{index}", post["read_time"]).strip()
            post["published"] = request.form.get(f"post_published_{index}", post["published"]).strip()
            post["image"] = request.form.get(f"post_image_{index}", post.get("image", "")).strip()
            post["description"] = request.form.get(f"post_description_{index}", post["description"]).strip()
            post["intro"] = request.form.get(f"post_intro_{index}", post["intro"]).strip()
            post["body_html"] = request.form.get(f"post_body_html_{index}", post["body_html"]).strip()

        new_slug = request.form.get("new_post_slug", "").strip()
        new_title = request.form.get("new_post_title", "").strip()
        if new_slug and new_title:
            content["blog_posts"].append(
                {
                    "slug": new_slug,
                    "title": new_title,
                    "description": request.form.get("new_post_description", "").strip(),
                    "category": request.form.get("new_post_category", "Guides").strip() or "Guides",
                    "read_time": request.form.get("new_post_read_time", "5 min read").strip() or "5 min read",
                    "published": request.form.get("new_post_published", str(date.today())).strip() or str(date.today()),
                    "image": request.form.get("new_post_image", "").strip(),
                    "intro": request.form.get("new_post_intro", "").strip(),
                    "body_html": request.form.get("new_post_body_html", "<p>New article body.</p>").strip() or "<p>New article body.</p>",
                }
            )

        save_content(content)
        message = "Changes saved."

    return render_template(
        "editor.html",
        content=content,
        message=message,
        meta_title=f"{content['site']['name']} Editor",
        meta_description="Edit homepage and blog content from one admin-style page.",
        editor_slug=EDITOR_SLUG,
        upload_url=url_for("editor_upload_image"),
        canonical_url=url_for("editor", _external=True),
    )


@app.route(f"/{EDITOR_SLUG}/logout", methods=["POST"])
def editor_logout():
    require_editor_auth()
    session.pop(EDITOR_SESSION_KEY, None)
    return redirect(url_for("editor"))


@app.route(f"/{EDITOR_SLUG}/upload-image", methods=["POST"])
def editor_upload_image():
    require_editor_auth()
    file_storage = request.files.get("image")
    try:
        location = save_uploaded_image(file_storage)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"location": location})


@app.route("/editor")
def editor_hidden():
    abort(404)


@app.route("/about")
def about():
    return render_page("about")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    content = load_content()
    page = content["pages"]["contact"]
    errors = []
    success_message = ""
    email_sent = False
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        if not name:
            errors.append("Name is required.")
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        if not subject:
            errors.append("Subject is required.")
        if not message:
            errors.append("Message is required.")
        if not errors:
            messages = load_contact_messages()
            messages.append(
                {
                    "submitted_at": datetime.utcnow().isoformat() + "Z",
                    "name": name,
                    "email": email,
                    "subject": subject,
                    "message": message,
                }
            )
            save_contact_messages(messages)
            try:
                email_sent = send_contact_email(name, email, subject, message)
            except Exception:
                email_sent = False
            success_message = "Your message has been sent." if email_sent else "Your message has been saved. We will review it soon."

    canonical_url = url_for("contact", _external=True)
    return render_template(
        "contact.html",
        page=page,
        success_message=success_message,
        email_sent=email_sent,
        form_errors=errors,
        meta_title=f"{page['title']} | {content['site']['name']}",
        meta_description=page["description"],
        canonical_url=canonical_url,
        schema_json_ld=[page_schema(page["title"], page["description"], canonical_url)],
    )


@app.route("/privacy-policy")
def privacy():
    return render_page("privacy")


@app.route("/terms-and-conditions")
def terms():
    return render_page("terms")


@app.route("/disclaimer")
def disclaimer():
    return render_page("disclaimer")


@app.route("/editorial-guidelines")
def editorial():
    return render_page("editorial")


def render_page(page_key: str):
    content = load_content()
    page = content["pages"][page_key]
    canonical_url = url_for(
        {
            "about": "about",
            "privacy": "privacy",
            "terms": "terms",
            "disclaimer": "disclaimer",
            "editorial": "editorial",
        }[page_key],
        _external=True,
    )
    return render_template(
        "page.html",
        page=page,
        meta_title=f"{page['title']} | {content['site']['name']}",
        meta_description=page["description"],
        canonical_url=canonical_url,
        schema_json_ld=[page_schema(page["title"], page["description"], canonical_url)],
    )


@app.route("/blog")
def blog_index():
    content = load_content()
    canonical_url = url_for("blog_index", _external=True)
    return render_template(
        "blog_index.html",
        posts=content["blog_posts"],
        meta_title=f"{content['site']['name']} Blog | Transcript Guides and SEO Content Ideas",
        meta_description="Browse transcript tutorials, SEO articles, and practical publishing workflows.",
        canonical_url=canonical_url,
        meta_image=content["blog_posts"][0].get("image", ""),
        schema_json_ld=[page_schema("Blog", "Transcript tutorials and publishing workflows.", canonical_url)],
    )


@app.route("/blog/<slug>")
def blog_post(slug: str):
    content = load_content()
    post = get_blog_post(content["blog_posts"], slug)
    if not post:
        abort(404)
    related = [item for item in content["blog_posts"] if item["slug"] != slug][:2]
    body_html, toc = add_heading_ids(post["body_html"])
    post_view = dict(post)
    post_view["body_html"] = body_html
    canonical_url = url_for("blog_post", slug=slug, _external=True)
    meta_image = post.get("image", "")
    return render_template(
        "blog_post.html",
        post=post_view,
        related_posts=related,
        toc=toc,
        author_name="U2btools Editorial Team",
        updated_label=post["published"],
        meta_title=f"{post['title']} | {content['site']['name']} Blog",
        meta_description=post["description"],
        canonical_url=canonical_url,
        meta_image=meta_image,
        schema_json_ld=[article_schema(post, canonical_url, meta_image)],
    )


@app.route("/robots.txt")
def robots():
    content = load_content()
    lines = ["User-agent: *", "Allow: /", "", f"Sitemap: {content['site']['domain']}/sitemap.xml"]
    return app.response_class("\n".join(lines), mimetype="text/plain")


@app.route("/ads.txt")
def ads():
    publisher_id = os.environ.get("U2BTOOLS_ADSENSE_PUB_ID", "pub-XXXXXXXXXXXXXXXX")
    return app.response_class(
        f"google.com, {publisher_id}, DIRECT, f08c47fec0942fa0",
        mimetype="text/plain",
    )


@app.route("/sitemap.xml")
def sitemap():
    content = load_content()
    routes = [
        url_for("index", _external=True),
        url_for("about", _external=True),
        url_for("contact", _external=True),
        url_for("privacy", _external=True),
        url_for("terms", _external=True),
        url_for("disclaimer", _external=True),
        url_for("editorial", _external=True),
        url_for("blog_index", _external=True),
    ]
    routes.extend(url_for("blog_post", slug=post["slug"], _external=True) for post in content["blog_posts"])
    xml = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for route in routes:
        xml.append("  <url>")
        xml.append(f"    <loc>{route}</loc>")
        xml.append("  </url>")
    xml.append("</urlset>")
    return app.response_class("\n".join(xml), mimetype="application/xml")


if __name__ == "__main__":
    app.run(debug=True)
