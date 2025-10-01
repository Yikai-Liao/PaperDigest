"""
Convert LaTeX JSON structure to Markdown.
Adapted from PaperDigestAction project.
"""
import json
import re
import logging

# Configure logging for debug mode
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for footnotes
footnotes = []
footnote_counter = 0
processed_titles = set()

def json_to_markdown(json_data, ignore_reference=False, clean_equations=False, debug=False):
    """Convert a JSON dictionary to a Markdown string."""
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    global footnotes, footnote_counter, processed_titles
    footnotes = []
    footnote_counter = 0
    processed_titles = set()
    tokens = json_data.get("tokens", [])
    md_content = process_tokens(tokens, is_top_level=True, ignore_reference=ignore_reference, clean_equations=clean_equations)
    if footnotes:
        md_content += "\n\n" + "\n".join(footnotes)
    return md_content

def process_tokens(tokens, is_top_level=False, ignore_reference=False, clean_equations=False):
    """Process a list of tokens and return Markdown string."""
    md_parts = []
    for token in tokens:
        token_type = token.get("type")
        if token_type == "title":
            md_parts.append(process_title(token, ignore_reference))
        elif token_type == "author":
            md_parts.append(process_author(token))
        elif token_type == "abstract":
            md_parts.append(process_abstract(token, ignore_reference))
        elif token_type == "section":
            md_parts.append(process_section(token, ignore_reference, clean_equations))
        elif token_type == "paragraph":
            md_parts.append(process_paragraph(token, ignore_reference, clean_equations))
        elif token_type == "list":
            md_parts.append(process_list(token, ignore_reference, clean_equations))
        elif token_type == "figure":
            md_parts.append(process_figure(token))
        elif token_type == "table":
            md_parts.append(process_table(token, ignore_reference))
        elif token_type == "equation":
            md_parts.append(process_equation(token, clean_equations))
        elif token_type == "citation":
            if not ignore_reference:
                md_parts.append(process_citation(token))
            continue  # Explicitly skip citations when ignore_reference=True
        elif token_type == "footnote":
            md_parts.append(process_footnote(token, ignore_reference, clean_equations))
        elif token_type == "bibliography" and not ignore_reference:
            md_parts.append(process_bibliography(token, ignore_reference))
        elif token_type == "text":
            if not is_top_level:
                md_parts.append(process_text(token))
            continue  # Skip top-level text tokens
        elif token_type == "command":
            continue  # Ignore LaTeX/IEEE commands
        elif token_type == "document":
            md_parts.append(process_tokens(token.get("content", []), is_top_level=False, ignore_reference=ignore_reference, clean_equations=clean_equations))
        elif token_type == "group":
            md_parts.append(process_tokens(token.get("content", []), is_top_level=False, ignore_reference=ignore_reference, clean_equations=clean_equations))
        elif token_type == "ref":
            md_parts.append(f"[{token.get('content', [''])[0]}]")
        elif token_type == "math_env":
            md_parts.append(process_math_env(token, ignore_reference, clean_equations))
        else:
            md_parts.append(f"<!-- Unknown token type: {token_type} -->")
    return "".join(md_parts)  # No extra newlines between tokens

def process_title(token, ignore_reference):
    """Convert title token to Markdown."""
    global processed_titles
    content = process_content(token.get("content", []), ignore_reference=ignore_reference)
    if content in processed_titles:
        return ""  # Skip duplicate titles
    processed_titles.add(content)
    return f"# {content}\n"

def process_author(token):
    """Convert author token to Markdown."""
    md_parts = []
    current_author = []
    current_superscripts = []
    for author_group in token.get("content", []):
        for item in author_group if isinstance(author_group, list) else [author_group]:
            if item.get("type") == "text":
                text = item.get("content", "").strip()
                # Handle combined name and punctuation (e.g., ", Anna Bielawska")
                if text.startswith(","):
                    if current_author or current_superscripts:
                        if current_superscripts:
                            current_author.append(f"<sup>{','.join(current_superscripts)}</sup>")
                            current_superscripts = []
                        md_parts.append("".join(current_author))
                        current_author = []
                    text = text.lstrip(",").strip()
                    if not text:
                        continue
                # Skip empty or punctuation-only tokens
                if not text or text in [",", ";"]:
                    continue
                styles = item.get("styles", [])
                # Handle author names (no superscript) and superscripts
                if "superscript" in styles:
                    current_superscripts.append(text)
                else:
                    if current_superscripts:
                        current_author.append(f"<sup>{','.join(current_superscripts)}</sup>")
                        current_superscripts = []
                    current_author.append(f"<b>{text}</b>")
            elif item.get("type") == "url":
                title = process_content(item.get("title", []), ignore_reference=False)
                current_author.append(f"[{title}]({item['content']})")
        if current_author or current_superscripts:
            if current_superscripts:
                current_author.append(f"<sup>{','.join(current_superscripts)}</sup>")
            md_parts.append("".join(current_author))
            current_author = []
            current_superscripts = []
    return "## Authors\n" + ", ".join(md_parts) + "\n" if md_parts else ""

def process_abstract(token, ignore_reference):
    """Convert abstract token to Markdown."""
    content = process_content(token.get("content", []), ignore_reference=ignore_reference)
    return "## Abstract\n" + content + "\n" if content else ""

def process_section(token, ignore_reference, clean_equations):
    """Convert section token to Markdown."""
    level = token.get("level", 1)
    numbering = token.get("numbering", "")
    title = process_content(token.get("title", []), ignore_reference=ignore_reference)
    if numbering:
        title = f"{numbering}. {title}"
    content = process_tokens(token.get("content", []), is_top_level=False, ignore_reference=ignore_reference, clean_equations=clean_equations)
    return f"{'#' * (level + 1)} {title}\n{content}\n" if title or content else ""

def process_paragraph(token, ignore_reference, clean_equations):
    """Convert paragraph token to Markdown."""
    content = process_tokens(token.get("content", []), is_top_level=False, ignore_reference=ignore_reference, clean_equations=clean_equations)
    return content + "\n\n" if content else ""  # Double newline for paragraph spacing

def process_list(token, ignore_reference, clean_equations):
    """Convert list token to Markdown."""
    items = []
    for item in token.get("content", []):
        item_content = process_tokens(item.get("content", []), is_top_level=False, ignore_reference=ignore_reference, clean_equations=clean_equations)
        if token.get("name") == "enumerate":
            items.append(f"{token.get('depth', 0) * '  '}1. {item_content}")
        else:
            items.append(f"{token.get('depth', 0) * '  '}- {item_content}")
    return "\n".join(items) + "\n" if items else ""

def process_figure(token):
    """Convert figure token to Markdown as a placeholder with caption."""
    content = token.get("content", [])
    numbering = token.get("numbering", "")
    caption = ""
    for item in content:
        if isinstance(item, dict) and item.get("type") == "caption":
            caption = process_content(item.get("content", []), ignore_reference=False)
            break
    return f"[Figure {numbering}]: {caption}\n" if caption else ""

def process_table(token, ignore_reference):
    """Convert table token to Markdown or retain JSON if complex."""
    content = token.get("content", [])
    caption = ""
    for item in content:
        if isinstance(item, dict) and item.get("type") == "caption":
            caption = process_content(item.get("content", []), ignore_reference=ignore_reference)
            break
    if not content or "tabular" not in content[0]:
        return f"[Table {token.get('numbering', '')}]: {caption}\nFollowing table is represented in JSON:\n```json\n{json.dumps(token, separators=(',', ':'), indent=None)}\n```\n"
    tabular = content[0].get("tabular", [])
    has_complex_attrs = any(
        cell.get("rowspan") or cell.get("colspan")
        for row in tabular for cell in row if isinstance(cell, dict)
    )
    if has_complex_attrs or not tabular:
        return f"[Table {token.get('numbering', '')}]: {caption}\nFollowing table is represented in JSON:\n```json\n{json.dumps(token, separators=(',', ':'), indent=None)}\n```\n"
    else:
        rows = []
        for row in tabular:
            row_cells = []
            for cell in row:
                if cell is None:
                    row_cells.append("")
                elif isinstance(cell, dict):
                    row_cells.append(process_content(cell.get("content", []), ignore_reference=ignore_reference))
                elif isinstance(cell, list):
                    row_cells.append(process_tokens(cell, is_top_level=False, ignore_reference=ignore_reference))
                else:
                    row_cells.append(str(cell))
            row_md = "| " + " | ".join(row_cells) + " |"
            rows.append(row_md)
        if len(rows) > 1:
            header_separator = "|-" + "-|-".join(["-" for _ in rows[0].split("|")[1:-1]]) + "-|"
            return f"[Table {token.get('numbering', '')}]: {caption}\n" + "\n".join([rows[0], header_separator] + rows[1:]) + "\n"
        return ""

def process_equation(token, clean_equations):
    """Convert equation token to Markdown, optionally cleaning problematic commands."""
    content = token.get("content", "").strip()
    if clean_equations:
        # Remove non-standard LaTeX commands like \command[optional]{arg1}{arg2}
        content = re.sub(r"\\[a-zA-Z]+\[.*?]\{.*?\}\{.*?\}", "", content)
        # Remove nested $$ or $
        content = re.sub(r"\$\$", "", content)
        content = re.sub(r"\$", "", content)
    logger.debug(f"Processing equation: {content}")
    if token.get("display") == "block":
        return f"$$ {content} $$\n"
    else:
        return f"${content}$"

def process_citation(token):
    """Convert citation token to Markdown."""
    content = token.get("content", [])
    title = process_content(token.get("title", []), ignore_reference=False)
    if title:
        return f"[{', '.join(content)}, {title}]"
    return f"[{', '.join(content)}]"

def process_footnote(token, ignore_reference, clean_equations):
    """Convert footnote token to Markdown."""
    global footnote_counter
    footnote_counter += 1
    content = process_tokens(token.get("content", []), is_top_level=False, ignore_reference=ignore_reference, clean_equations=clean_equations)
    footnotes.append(f"[^{footnote_counter}]: {content}")
    return f"[^{footnote_counter}]"

def process_bibliography(token, ignore_reference):
    """Convert bibliography token to Markdown."""
    bib_items = []
    for item in token.get("content", []):
        cite_key = item.get("cite_key", "")
        content = process_content(item.get("content", []), ignore_reference=ignore_reference)
        bib_items.append(f"[{cite_key}]: {content}")
    return "## References\n" + "\n".join(bib_items) + "\n" if bib_items else ""

def process_text(token):
    """Convert text token to Markdown with styles."""
    text = token.get("content", "")
    styles = token.get("styles", [])
    if "bold" in styles and "italic" in styles:
        text = f"<b><i>{text}</i></b>"
    elif "bold" in styles:
        text = f"<b>{text}</b>"
    elif "italic" in styles:
        text = f"<i>{text}</i>"
    return text

def process_math_env(token, ignore_reference, clean_equations):
    """Convert math_env token to Markdown."""
    content = token.get("content", "")
    if isinstance(content, list):
        content = process_content(content, ignore_reference=ignore_reference).strip()
    else:
        content = content.strip()
    logger.debug(f"Processing math_env: {content}")
    if content:
        if content.startswith("\\begin{"):
            return f"$$ {content} $$\n"
        return f"{content}\n"
    return ""

def process_content(content, ignore_reference=False):
    """Recursively process content field."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        return "".join(process_tokens(content, is_top_level=False, ignore_reference=ignore_reference))
    return ""
