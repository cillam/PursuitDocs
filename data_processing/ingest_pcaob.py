import requests
from bs4 import BeautifulSoup, NavigableString
import json
import os
import re
import time
from datetime import datetime


to_scrape = ["https://pcaobus.org/oversight/standards/auditing-standards", 
             "https://pcaobus.org/about/rules-rulemaking/rules/section_3", 
             "https://pcaobus.org/resources/information-for-investors/investor-advisories/investor-bulletin--the-importance-of-auditor-professional-responsibilities-and-ethics"
             ]

HEADERS = {"User-Agent": "Mozilla/5.0"}
REQUEST_DELAY = 1

BASE_DIR = os.path.join("..", "data", "pcaob_content")
STANDARDS_DIR = os.path.join(BASE_DIR, "standards")
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
    for directory in [STANDARDS_DIR, BULLETINS_DIR, SPOTLIGHTS_DIR]:
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
    current_heading = None
    current_parent = None
    current_level = None
    current_content_parts = []
    current_footnote_refs = []

    heading_tags = {"h2", "h3"}
    content_tags = {"p", "ol", "ul", "table", "blockquote"}

    for element in content_div.children:
        if isinstance(element, NavigableString):
            continue

        if element.name in heading_tags:
            # Save previous section
            if current_heading is not None:
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
                current_parent = None
                current_level = 2
            elif element.name == "h3":
                current_parent = last_h2
                current_level = 3

        elif element.name in content_tags and current_heading is not None:
            # Collect footnote refs from this element
            for fn_ref in element.find_all("a", attrs={"name": re.compile(r"^_ftnref")}):
                sup = fn_ref.find("sup")
                if sup:
                    current_footnote_refs.append(sup.get_text(strip=True))
                fn_ref.replace_with(" ")

            text = element.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text).strip()
            text = text.replace(" .", ".")
            if text:
                current_content_parts.append(text)

    # Save last section
    if current_heading is not None:
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
                print(f"\nScraping spotlight: {addy}")
                data = parse_pdf_content(addy)
                filename = addy.split("/")[-1].split("?")[0].replace(".pdf", ".json")
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
                    save_json(rule_data, STANDARDS_DIR, filename)

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