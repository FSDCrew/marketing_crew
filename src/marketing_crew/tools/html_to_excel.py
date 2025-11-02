from crewai.tools import tool
from bs4 import BeautifulSoup
import xlsxwriter
import os

def _parse_html_table_with_spans(html: str):
    """
    Returns: grid (list[list[str]]), merges (list[(r1, c1, r2, c2, value)])
    grid is a rectangular 0-based matrix of strings.
    merges contains inclusive cell coordinates for ranges to merge in Excel.
    """
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        raise ValueError("No <table> found in HTML.")

    # Build a grid honoring row/col spans
    grid = []
    merges = []
    col_count = 0
    occupied = {}  # (r, c) -> True    tracks cells covered by prior rowspans

    rows = table.find_all("tr")
    for r_idx, tr in enumerate(rows):
        # Ensure grid has this row
        while len(grid) <= r_idx:
            grid.append([])
        row = grid[r_idx]

        # Extend current row to account for carried-over rowspans
        c_idx = 0
        while c_idx < col_count:
            if (r_idx, c_idx) in occupied:
                # Placeholder for a covered cell (will be filled with "")
                row.append("")
            else:
                row.append(None)  # free slot to fill
            c_idx += 1

        cells = tr.find_all(["td", "th"])
        c_ptr = 0
        for cell in cells:
            # Move c_ptr to next free column (skip occupied)
            while True:
                if len(row) <= c_ptr:
                    row.append(None)
                # Skip columns occupied by a rowspan from above
                if (r_idx, c_ptr) in occupied:
                    if row[c_ptr] == None:
                        row[c_ptr] = ""
                    c_ptr += 1
                    continue
                break

            text = cell.get_text(separator=" ", strip=True)
            rs = int(str(cell.get("rowspan", "1")))
            cs = int(str(cell.get("colspan", "1")))


            # Make sure grid rows have enough columns
            needed_cols = c_ptr + cs
            col_count = max(col_count, needed_cols)
            while len(row) < needed_cols:
                row.append(None)

            # Place the top-left value
            row[c_ptr] = text

            # Mark merge if span>1
            if rs > 1 or cs > 1:
                r1, c1 = r_idx, c_ptr
                r2, c2 = r_idx + rs - 1, c_ptr + cs - 1
                merges.append((r1, c1, r2, c2, text))

            # Mark covered cells (rightwards in this row)
            for dc in range(cs):
                if dc == 0:
                    continue
                if row[c_ptr + dc] is None:
                    row[c_ptr + dc] = ""
            # Mark occupied for future rows (downwards)
            for dr in range(1, rs):
                rr = r_idx + dr
                for dc in range(cs):
                    cc = c_ptr + dc
                    occupied[(rr, cc)] = True

            c_ptr += cs

        # Replace remaining None with "" and pad to col_count
        for i in range(len(row)):
            if row[i] is None:
                row[i] = ""
        while len(row) < col_count:
            row.append("")

    # Ensure all rows have equal columns
    for r in grid:
        while len(r) < col_count:
            r.append("")
    return grid, merges

@tool("HTML to Excel Converter (with spans)")
def html_to_excel_tool(
    html_str: str,
    # output_path: str | None = None
) -> str:
    """
    Converts an HTML table string into an Excel (.xlsx) file with row/col spans preserved as merged cells.
    Only the first <table> is processed.
    """
    # output_path = output_path or "./output/html_to_excel.xlsx"
    output_path = "./output/html_to_excel.xlsx"
    try:
        grid, merges = _parse_html_table_with_spans(html_str)

        # Ensure output dir exists
        outdir = os.path.dirname(output_path) or "."
        os.makedirs(outdir, exist_ok=True)

        # Write with XlsxWriter and apply merges
        workbook = xlsxwriter.Workbook(output_path)
        worksheet = workbook.add_worksheet("Schedule")

        # Optional formatting
        header_fmt = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1})
        cell_fmt = workbook.add_format({"text_wrap": True, "valign": "top", "border": 1})

        # Write cells
        for r, row in enumerate(grid):
            for c, val in enumerate(row):
                # Heuristic: first row as header if <th> used in HTML; if not sure, just use cell_fmt for all
                fmt = cell_fmt
                if r == 0:  # treat first row as header for simplicity
                    fmt = header_fmt
                worksheet.write(r, c, val, fmt)

        # Apply merges (XlsxWriter uses inclusive ranges, 0-based)
        for r1, c1, r2, c2, val in merges:
            # Pick header vs cell format based on r1 (top-left row)
            fmt = header_fmt if r1 == 0 else cell_fmt
            worksheet.merge_range(r1, c1, r2, c2, val, fmt)

        # Autosize columns a bit
        for c in range(len(grid[0]) if grid else 0):
            # simple width guess
            max_len = max((len(str(grid[r][c])) for r in range(len(grid))), default=10)
            worksheet.set_column(c, c, min(60, max(12, max_len * 0.9)))

        workbook.close()
        return f"✅ Excel file (with merged cells) saved at: {output_path}"
    except Exception as e:
        return f"❌ Error converting HTML to Excel with spans: {e}"

if __name__ == "__main__":
    html_str = """
    <table border="1" cellpadding="6" cellspacing="0">
        <thead>
            <tr>
            <th>Week</th>
            <th>Posting Cadence</th>
            <th>Post Type</th>
            <th>Date</th>
            <th>Theme/Concept</th>
            <th>Objective</th>
            <th>Description</th>
            <th>Notes</th>
            </tr>
        </thead>
        <tbody>
            <!-- Week 1 (5 rows = 3 posts + 2 stories) -->
            <tr>
            <td rowspan="5">1</td>
            <td rowspan="5">3 posts, 2 stories; Post times 11am, 6pm</td>
            <td>Post</td>
            <td>01-Nov-2025</td>
            <td>Welcome to Semester &amp; Campus Life</td>
            <td>Kickstart engagement; introduce semester vibe</td>
            <td>Vibrant shots of campus, student groups &amp; iconic spots</td>
            <td>Canva templates ready</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>03-Nov-2025</td>
            <td>Campus Life Highlights</td>
            <td>Showcase energetic environment and increase relatability</td>
            <td>Student life &amp; campus hotspots reel</td>
            <td>Include trending audio</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>05-Nov-2025</td>
            <td>Clubs &amp; Student Culture</td>
            <td>Increase awareness of extracurricular opportunities</td>
            <td>Spotlight on student clubs &amp; culture</td>
            <td>Highlight campus diversity</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>02-Nov-2025</td>
            <td>Welcome Season</td>
            <td>Share excitement in real-time and drive early engagement</td>
            <td>Orientation welcome snippets</td>
            <td>Tag student ambassadors</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>04-Nov-2025</td>
            <td>Excitement Polls</td>
            <td>Gather insights on what students want content about</td>
            <td>Poll: “What are you most excited for?”</td>
            <td>Campus GIF stickers</td>
            </tr>

            <!-- Week 2 (8 rows = 3 posts + 5 stories) -->
            <tr>
            <td rowspan="8">2</td>
            <td rowspan="8">3 posts, 5 stories; Post times 12pm, 7pm</td>
            <td>Post</td>
            <td>07-Nov-2025</td>
            <td>Signature Events Preview</td>
            <td>Build excitement for upcoming campus festivals</td>
            <td>Teasers of festival themes &amp; prep visuals</td>
            <td>Add countdown sticker</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>09-Nov-2025</td>
            <td>Festival Hype</td>
            <td>Boost anticipation and awareness of main highlights</td>
            <td>Hype poster for main festival highlight</td>
            <td>Include teaser CTA</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>11-Nov-2025</td>
            <td>Throwback Inspiration</td>
            <td>Use nostalgia and credibility to encourage RSVPs</td>
            <td>Trailer/snippets from past editions</td>
            <td>Encourage RSVPs</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>08-Nov-2025</td>
            <td>Behind the Scenes</td>
            <td>Provide insider access to drive engagement</td>
            <td>Behind-the-scenes look</td>
            <td>Tag organising committee</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>10-Nov-2025</td>
            <td>Event Voices</td>
            <td>Increase participation by spotlighting student opinions</td>
            <td>Quick vox pops on favourite past events!</td>
            <td>Include Swipe-up link</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>12-Nov-2025</td>
            <td>Talent &amp; Vendor Showcase</td>
            <td>Promote partners/performers to drive festival credibility</td>
            <td>Sneak peek on vendors/performers</td>
            <td>Short Q&amp;A quiz</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>13-Nov-2025</td>
            <td>Anticipation Polls</td>
            <td>Capture preferences for better CG-led event content</td>
            <td>Poll: favourite activity to attend</td>
            <td>Encourage sharing</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>14-Nov-2025</td>
            <td>Guess the Performer</td>
            <td>Gamify engagement with curiosity hooks</td>
            <td>Trivia: Guess who’s performing?</td>
            <td>Reveal tomorrow</td>
            </tr>

            <!-- Week 3 (9 rows = 3 posts + 6 stories) -->
            <tr>
            <td rowspan="9">3</td>
            <td rowspan="9">3 posts, 6 stories; Post times 11am, 5pm</td>
            <td>Post</td>
            <td>15-Nov-2025</td>
            <td>Student-Generated Content Showcase</td>
            <td>Empower student voices &amp; creativity</td>
            <td>Feature standout student works</td>
            <td>Include submission CTA</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>17-Nov-2025</td>
            <td>Creative Spotlight</td>
            <td>Highlight the diversity of student talent</td>
            <td>Carousel: Student art/design highlights</td>
            <td>Tag creators</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>19-Nov-2025</td>
            <td>Creator Deep Dive</td>
            <td>Increase relatability through personal storytelling</td>
            <td>Short-format documentary clip of a creator</td>
            <td>High-share value</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>16-Nov-2025</td>
            <td>Creator Journey</td>
            <td>Humanise creations and inspire participation</td>
            <td>Behind-the-scenes of creators</td>
            <td>Tag participants</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>18-Nov-2025</td>
            <td>Live Feature Voting</td>
            <td>Boost real-time participation and feedback</td>
            <td>Live voting prompt for features</td>
            <td>Engagement sticker</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>20-Nov-2025</td>
            <td>Project Selection Poll</td>
            <td>Drive decision-making engagement</td>
            <td>Poll: which project to feature next?</td>
            <td>Encourage reposts</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>21-Nov-2025</td>
            <td>Student Showcase Highlights</td>
            <td>Sustain momentum around creative submissions</td>
            <td>Slideshow of student entries</td>
            <td>Include CTA to vote/share</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>22-Nov-2025</td>
            <td>Creator Introductions</td>
            <td>Help audience connect with featured students</td>
            <td>“Meet the creator” mini interviews</td>
            <td>Add handle mentions</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>23-Nov-2025</td>
            <td>Showcase Countdown</td>
            <td>Build hype toward final reveal</td>
            <td>Countdown to final showcase post</td>
            <td>Build hype</td>
            </tr>
        </tbody>
        </table>

    """
    print(html_to_excel_tool.func(html_str=html_str))