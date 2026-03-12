import requests
from bs4 import BeautifulSoup, NavigableString
import pdfplumber
import json
import os
import re
import time
import tempfile
from datetime import datetime


to_scrape = ["https://pcaobus.org/oversight/standards/auditing-standards", 
             "https://pcaobus.org/about/rules-rulemaking/rules/section_3", 
             "https://assets.pcaobus.org/pcaob-dev/docs/default-source/documents/auditor-independence-spotlight.pdf", 
             "https://pcaobus.org/resources/information-for-investors/investor-advisories/investor-bulletin--the-importance-of-auditor-professional-responsibilities-and-ethics"
             ]

HEADERS = {"User-Agent": "Mozilla/5.0"}
REQUEST_DELAY = 1

BASE_DIR = os.path.join("..", "data", "pcaob_content")
STANDARDS_DIR = os.path.join(BASE_DIR, "standards")
RULES_DIR = os.path.join(BASE_DIR, "rules")
BULLETINS_DIR = os.path.join(BASE_DIR, "bulletins")
SPOTLIGHTS_DIR = os.path.join(BASE_DIR, "spotlights")

INCLUDED_STANDARDS = {
    "AS 1000", "AS 1101", "AS 1105", "AS 1110",
    "AS 1201", "AS 1206", "AS 1210", "AS 1215", "AS 1220",
    "AS 1301", "AS 1305",
}

INCLUDED_RULES = {
    "Rule 3501", "Rule 3502", "Rule 3520", "Rule 3521",
    "Rule 3522", "Rule 3523", "Rule 3524", "Rule 3525", "Rule 3526",
}


def setup_directories():
    for directory in [STANDARDS_DIR, RULES_DIR, BULLETINS_DIR, SPOTLIGHTS_DIR]:
        os.makedirs(directory, exist_ok=True)


def should_scrape_standard(title: str) -> bool:
    match = re.match(r"(AS\s*\d+)", title)
    if match:
        std_num = re.sub(r"\s+", " ", match.group(1))
        return std_num in INCLUDED_STANDARDS
    return False


def scrape_pcaob_standards_index(url: str):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    container = soup.find("div", id="Main_T92A60133009_Col01")
    if not container:
        raise ValueError("Main content container not found")

    results = []
    current_section = None
    current_subsection = None

    for element in container.descendants:

        if element.name == "h2":
            current_section = element.get_text(strip=True)
            current_subsection = None

        elif element.name == "h3":
            current_subsection = element.get_text(strip=True)

        elif element.name == "a":
            href = element.get("href", "")

            if "/auditing-standards/details/" in href or "/about/rules-rulemaking/rules/" in href or "/ethics-independence-rules/details/" in href:
                if not href.startswith("http"):
                    href = "https://pcaobus.org" + href

                results.append({
                    "section": current_section,
                    "subsection": current_subsection,
                    "title": element.get_text(strip=True),
                    "url": href
                })

    return results


def format_table(table: list) -> str:
    """Format a pdfplumber table (list of rows) into readable text."""
    if not table or len(table) < 2:
        return ""

    rows = []
    for row in table:
        # Clean up each cell
        cleaned = []
        for cell in row:
            if cell is None:
                cleaned.append("")
            else:
                # Collapse whitespace within cells
                cleaned.append(re.sub(r"\s+", " ", cell).strip())
        rows.append(cleaned)

    # Format as "Header1 | Header2" followed by "Value1 | Value2"
    lines = []
    for row in rows:
        lines.append(" | ".join(row))

    return "\n".join(lines)


def parse_pdf_content(url: str):
    """Download a PDF, extract text with pdfplumber, delete the PDF."""
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(r.content)
    tmp.close()

    try:
        # Extract text and tables per page
        page_texts = {}
        page_tables = {}
        with pdfplumber.open(tmp.name) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    page_texts[page.page_number] = text

                tables = page.extract_tables()
                if tables:
                    page_tables[page.page_number] = tables

        filename = url.split("/")[-1].split("?")[0]
        title = filename.replace(".pdf", "").replace("-", " ").title()

        # TOC structure for the Auditor Independence Spotlight
        # TODO: Replace with font-based heading detection for general use
        toc = [
            {"heading": "Overview", "page": 3, "parent": None, "level": 1},
            {"heading": "Auditor Independence: Importance and Recent Trends", "page": 3, "parent": None, "level": 1},
            {"heading": "PCAOB Inspection Procedures Related to Independence", "page": 6, "parent": None, "level": 1},
            {"heading": "Focus Areas", "page": 6, "parent": "PCAOB Inspection Procedures Related to Independence", "level": 2},
            {"heading": "Inspection Observations Related to Independence", "page": 8, "parent": None, "level": 1},
            {"heading": "Audit Committee Pre-Approval of Services/Communication With the Audit Committee", "page": 8, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Independence Representations/Personal Independence Compliance Testing", "page": 11, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Prohibited Financial Relationships", "page": 13, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Permissibility of Non-Audit and Tax Services", "page": 15, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Business and Employment Relationships", "page": 17, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Indemnification Clauses", "page": 19, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Independence Policies", "page": 20, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Partner Rotation", "page": 22, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Restricted Entity List", "page": 23, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Contingent Fees", "page": 24, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Mutual Interest - Unpaid Fees", "page": 24, "parent": "Inspection Observations Related to Independence", "level": 2},
            {"heading": "Good Practices", "page": 26, "parent": None, "level": 1},
            {"heading": "Reminders for Auditors", "page": 27, "parent": None, "level": 1},
            {"heading": "Audit Committee Considerations", "page": 28, "parent": None, "level": 1},
            {"heading": "Appendix: PCAOB Inspection Categories", "page": 29, "parent": None, "level": 1},
            {"heading": "Global Network Firm (GNF)", "page": 29, "parent": "Appendix: PCAOB Inspection Categories", "level": 2},
            {"heading": "Non-Affiliate Firm (NAF)", "page": 29, "parent": "Appendix: PCAOB Inspection Categories", "level": 2},
            {"heading": "Broker-Dealer Firms", "page": 29, "parent": "Appendix: PCAOB Inspection Categories", "level": 2},
        ]

        max_page = max(page_texts.keys()) if page_texts else 0

        # Build sections by extracting text between each TOC entry's page and the next
        sections = []
        for i, entry in enumerate(toc):
            start_page = entry["page"]

            # End page is the page before the next section starts (or last page)
            if i + 1 < len(toc):
                end_page = toc[i + 1]["page"]
                # If next section starts on same page, they share the page
                if end_page == start_page:
                    end_page = start_page
                else:
                    end_page = end_page - 1
            else:
                end_page = max_page

            # Collect text from the page range
            section_text_parts = []
            for pg in range(start_page, end_page + 1):
                if pg in page_texts:
                    section_text_parts.append(page_texts[pg])

            full_section_text = "\n\n".join(section_text_parts).strip()

            # Try to isolate just this section's text when sharing a page
            # by finding the heading in the text and taking from there
            heading = entry["heading"]
            if full_section_text and heading in full_section_text:
                idx = full_section_text.index(heading)
                # If there's a next section on the same end page, cut at that heading
                if i + 1 < len(toc) and toc[i + 1]["page"] <= end_page:
                    next_heading = toc[i + 1]["heading"]
                    if next_heading in full_section_text[idx + len(heading):]:
                        next_idx = full_section_text.index(next_heading, idx + len(heading))
                        full_section_text = full_section_text[idx + len(heading):next_idx].strip()
                    else:
                        full_section_text = full_section_text[idx + len(heading):].strip()
                else:
                    full_section_text = full_section_text[idx + len(heading):].strip()

            # Clean up whitespace
            full_section_text = re.sub(r"\s+", " ", full_section_text).strip()

            # Collect tables from the page range
            section_tables = []
            for pg in range(start_page, end_page + 1):
                if pg in page_tables:
                    for table in page_tables[pg]:
                        formatted = format_table(table)
                        if formatted:
                            section_tables.append(formatted)

            sections.append({
                "heading": heading,
                "parent": entry["parent"],
                "level": entry["level"],
                "content": full_section_text,
                "tables": section_tables,
                "footnote_refs": [],
            })

        return {
            "metadata": {
                "title": title,
                "url": url,
                "document_type": "spotlight",
                "scraped_at": datetime.now().isoformat(),
            },
            "footnotes": {},
            "content": sections,
        }
    finally:
        os.unlink(tmp.name)


def parse_html_content(url: str, index_metadata: dict = None):
    """Scrape and parse an HTML page (standard or bulletin)."""
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # --- Metadata ---
    title_tag = soup.find("h1")
    full_title = title_tag.get_text(strip=True) if title_tag else ""

    standard_num_match = re.match(r"(AS\s*\d+|Rule\s*\d+)", full_title)
    standard_number = standard_num_match.group(1) if standard_num_match else ""

    # --- Find main content container ---
    outer_div = soup.find("div", id="Main_T92A60133009_Col01")
    if not outer_div:
        raise ValueError(f"Could not find main content div at {url}")

    content_div = outer_div.find("div", class_="ms-rtestate-field")
    if not content_div:
        # Bulletin pages nest content in anonymous divs — find the one containing the h1
        h1 = outer_div.find("h1")
        if h1:
            content_div = h1.parent
        else:
            content_div = outer_div

    # --- Extract footnotes from div.footnotes ---
    footnotes = {}
    footnotes_div = content_div.find("div", class_="footnotes")
    if footnotes_div:
        for p in footnotes_div.find_all("p"):
            sup = p.find("sup")
            if sup:
                fn_num = sup.get_text(strip=True)
                # Get text with spaces preserved between tags
                fn_text = p.get_text(separator=" ", strip=True)
                # Strip the leading footnote number
                fn_text = re.sub(r"^\d+\s*", "", fn_text)
                # Clean up extra spaces from separator
                fn_text = re.sub(r"\s+", " ", fn_text).strip()
                if fn_text:
                    footnotes[fn_num] = fn_text
        footnotes_div.decompose()

    # --- Remove TOC accordion ---
    toc = content_div.find("div", class_="summaryAccordionZone")
    if toc:
        toc.decompose()

    # --- Remove sidebars ---
    for sidebar in content_div.find_all("table", class_="sidebar"):
        sidebar.decompose()

    # --- Walk direct children of content div for sections ---
    sections = []
    last_h2 = None
    # Use the standard title as default heading so content before any h2 is captured
    current_heading = full_title
    current_parent = None
    current_level = 1
    current_content_parts = []
    current_footnote_refs = []

    heading_tags = {"h2", "h3"}
    content_tags = {"p", "ol", "ul", "table", "blockquote"}

    for element in content_div.children:
        if isinstance(element, NavigableString):
            continue

        if element.name in heading_tags:
            # Save previous section
            if current_heading is not None and current_content_parts:
                sections.append({
                    "heading": current_heading,
                    "parent": current_parent,
                    "level": current_level,
                    "content": "\n\n".join(current_content_parts).strip(),
                    "footnote_refs": current_footnote_refs,
                })

            current_heading = element.get_text(strip=True)
            current_content_parts = []
            current_footnote_refs = []

            if element.name == "h2":
                last_h2 = current_heading
                current_parent = full_title
                current_level = 2
            elif element.name == "h3":
                current_parent = last_h2
                current_level = 3

        elif element.name in content_tags:
            # Collect footnote refs from this element
            def is_ftnref(tag):
                return tag.name == "a" and (
                    re.match(r"^_ftnref", tag.get("name", "")) or
                    re.match(r"^_ftnref", tag.get("id", "")))

            for fn_ref in element.find_all(is_ftnref):
                sup = fn_ref.find("sup")
                if sup:
                    num = sup.get_text(strip=True)
                    current_footnote_refs.append(num)
                    fn_ref.replace_with(f" [fn_{num}] ")
                else:
                    fn_ref.replace_with(f" ")

            text = element.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text).strip()
            text = text.replace(" . ", ". ")
            text = text.replace(" : ", ": ")
            if text:
                current_content_parts.append(text)

    # Save last section
    if current_heading is not None and current_content_parts:
        sections.append({
            "heading": current_heading,
            "parent": current_parent,
            "level": current_level,
            "content": "\n\n".join(current_content_parts).strip(),
            "footnote_refs": current_footnote_refs,
        })

    metadata = {
        "standard_number": standard_number,
        "title": full_title,
        "url": url,
        "scraped_at": datetime.now().isoformat(),
    }

    if index_metadata:
        metadata["section"] = index_metadata.get("section")
        metadata["subsection"] = index_metadata.get("subsection")
        metadata["document_type"] = "standard"
    else:
        metadata["document_type"] = "bulletin"

    return {
        "metadata": metadata,
        "footnotes": footnotes,
        "content": sections,
    }


def save_json(data: dict, directory: str, filename: str):
    filepath = os.path.join(directory, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {filepath}")


def parse_rules_page(url: str):
    """
    Parse the section_3 rules page, which contains multiple rules on one page.
    Splits each rule into its own JSON, returning a list of rule dicts.
    """
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # Remove sidebars
    sidebars = soup.find_all("table", class_="sidebar")
    for sidebar in sidebars:
        sidebar.decompose()

    # --- Find all h2 headings that are rules ---
    # Each h2 is a rule boundary. Collect content between h2s.
    all_h2s = soup.find_all("h2")

    rules = []
    content_tags = {"p", "ol", "ul", "table", "blockquote"}

    for i, h2 in enumerate(all_h2s):
        heading_text = h2.get_text(strip=True)
        if not heading_text:
            continue

        # Check if this is a rule we want
        rule_match = re.match(r"(Rule\s*\d+)", heading_text)
        if not rule_match:
            continue

        rule_number = re.sub(r"\s+", " ", rule_match.group(1))
        if rule_number not in INCLUDED_RULES:
            continue

        # Collect all content between this h2 and the next h2
        content_parts = []
        footnote_refs = []
        current_subsection = None
        sections = []

        # Walk siblings after this h2 until we hit the next h2
        sibling = h2.find_next_sibling()
        while sibling:
            if sibling.name == "h2":
                break

            if sibling.name == "h3":
                # Save previous subsection content if any
                if current_subsection is not None and content_parts:
                    sections.append({
                        "heading": current_subsection,
                        "parent": heading_text,
                        "level": 3,
                        "content": "\n\n".join(content_parts).strip(),
                        "footnote_refs": footnote_refs,
                    })
                    content_parts = []
                    footnote_refs = []

                current_subsection = sibling.get_text(strip=True)

            elif sibling.name in content_tags:
                # Collect footnote refs
                for fn_ref in sibling.find_all("a", attrs={"name": re.compile(r"^_ftnref")}):
                    sup = fn_ref.find("sup")
                    if sup:
                        footnote_refs.append(sup.get_text(strip=True))
                    fn_ref.replace_with(" ")

                text = sibling.get_text(separator=" ")
                text = re.sub(r"\s+", " ", text).strip()
                text = text.replace(" .", ".")
                if text:
                    content_parts.append(text)

            sibling = sibling.find_next_sibling()

        # Save remaining content
        if current_subsection is not None and content_parts:
            sections.append({
                "heading": current_subsection,
                "parent": heading_text,
                "level": 3,
                "content": "\n\n".join(content_parts).strip(),
                "footnote_refs": footnote_refs,
            })
        elif content_parts:
            # No subsections — all content belongs to the rule heading
            sections.append({
                "heading": heading_text,
                "parent": None,
                "level": 2,
                "content": "\n\n".join(content_parts).strip(),
                "footnote_refs": footnote_refs,
            })

        rule_data = {
            "metadata": {
                "standard_number": rule_number,
                "title": heading_text,
                "section": "Ethics & Independence Rules",
                "subsection": None,
                "url": url + "#" + (h2.find("a", attrs={"name": True}) or {}).get("name", rule_number.lower().replace(" ", "")),
                "document_type": "rule",
                "scraped_at": datetime.now().isoformat(),
            },
            "footnotes": {},
            "content": sections,
        }

        rules.append(rule_data)
        print(f"    Parsed: {rule_number} — {heading_text}")

    return rules


def generate_index(all_items: list):
    index = {
        "generated_at": datetime.now().isoformat(),
        "total_items": len(all_items),
        "items": all_items,
    }
    filepath = os.path.join(BASE_DIR, "index.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"\nIndex saved: {filepath} ({len(all_items)} items)")


if __name__ == "__main__":
    setup_directories()
    index_items = []

    try:
        for addy in to_scrape:
            if "spotlight" in addy:
                filename = addy.split("/")[-1].split("?")[0].replace(".pdf", ".json")
                filepath = os.path.join(SPOTLIGHTS_DIR, filename)

                # Check if the JSON already exists (manually created)
                if os.path.exists(filepath):
                    print(f"\nSpotlight already exists: {filepath}")
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                else:
                    print(f"\nScraping spotlight: {addy}")
                    data = parse_pdf_content(addy)
                    save_json(data, SPOTLIGHTS_DIR, filename)

                index_items.append({
                    "document_type": "spotlight",
                    "title": data["metadata"]["title"],
                })

            elif "bulletin" in addy:
                print(f"\nScraping bulletin: {addy}")
                data = parse_html_content(addy)
                title = data["metadata"]["title"]
                filename = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower() + ".json"
                save_json(data, BULLETINS_DIR, filename)
                index_items.append({
                    "document_type": "bulletin",
                    "title": data["metadata"]["title"],
                })

            elif "section_3" in addy:
                print(f"\nScraping rules page: {addy}")
                rules = parse_rules_page(addy)

                for rule_data in rules:
                    rule_num = rule_data["metadata"]["standard_number"]
                    filename = rule_num.replace(" ", "_") + ".json"
                    save_json(rule_data, RULES_DIR, filename)

                    index_items.append({
                        "document_type": "rule",
                        "standard_number": rule_num,
                        "title": rule_data["metadata"]["title"],
                        "section": "Ethics & Independence Rules",
                    })

            else:
                print(f"\nScraping standards index: {addy}")
                section_urls = scrape_pcaob_standards_index(addy)

                for item in section_urls:
                    if not should_scrape_standard(item["title"]):
                        continue

                    print(f"\n  Scraping: {item['title']}")
                    time.sleep(REQUEST_DELAY)
                    data = parse_html_content(item["url"], index_metadata=item)

                    std_num = data["metadata"]["standard_number"]
                    filename = std_num.replace(" ", "_") + ".json" if std_num else "unknown.json"
                    save_json(data, STANDARDS_DIR, filename)

                    index_items.append({
                        "document_type": "standard",
                        "standard_number": std_num,
                        "title": data["metadata"]["title"],
                        "section": item.get("section"),
                        "subsection": item.get("subsection"),
                    })

        generate_index(index_items)
        print("\n✅ Done!")

    except Exception as e:
        print(f"\n❌ Failed: {e}")
