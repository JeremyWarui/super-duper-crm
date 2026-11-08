// Post text as the site shows it: the cleaned HTML the editor writes.
import DOMPurify from "dompurify";
import { cn } from "@/lib/utils";

// The tags the backend keeps (services/rich_text.py); anything else is dropped before it shows.
const TAGS = ["p", "br", "h2", "h3", "strong", "em", "s", "a", "ul", "ol", "li", "blockquote", "img"];

/** Cleaned post HTML, drawn with the site's text styles. */
export function RichText({ html, className }) {
  const clean = DOMPurify.sanitize(html || "", { ALLOWED_TAGS: TAGS, ALLOWED_ATTR: ["href", "src", "alt", "rel"] });
  return <div className={cn("rich-text", className)} dangerouslySetInnerHTML={{ __html: clean }} />;
}

/** The text of each paragraph, list item or heading in the HTML, in order. */
export function paragraphs(html) {
  const doc = new DOMParser().parseFromString(html || "", "text/html");
  const blocks = [...doc.body.querySelectorAll("p, li, h2, h3, blockquote")].filter((el) => !el.querySelector("p, li"));
  const texts = (blocks.length ? blocks : [doc.body]).map((el) => el.textContent.trim());
  return texts.filter(Boolean);
}
