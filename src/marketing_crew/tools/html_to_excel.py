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

                # Ensure grid has enough rows to accommodate this rowspan
                max_row_needed = r_idx + rs
                while len(grid) < max_row_needed:
                    grid.append([])

            # Mark covered cells (rightwards in this row)
            for dc in range(cs):
                if dc == 0:
                    continue
                if row[c_ptr + dc] is None:
                    row[c_ptr + dc] = ""
            # Mark occupied for future rows (downwards)
            for dr in range(1, rs):
                rr = r_idx + dr
                # Ensure this row exists in grid and is properly initialized
                while len(grid) <= rr:
                    grid.append([])
                future_row = grid[rr]
                # Ensure future row has enough columns and mark occupied cells
                while len(future_row) < col_count:
                    future_row.append(None)
                for dc in range(cs):
                    cc = c_ptr + dc
                    occupied[(rr, cc)] = True
                    # Mark the occupied cell as empty string in the grid
                    if cc < len(future_row):
                        future_row[cc] = ""

            c_ptr += cs

        # Replace remaining None with "" and pad to col_count
        for i in range(len(row)):
            if row[i] is None:
                row[i] = ""
        while len(row) < col_count:
            row.append("")

    # Ensure all rows have equal columns and are properly initialized
    # This handles cases where rowspans extended beyond actual HTML rows
    for r_idx, r in enumerate(grid):
        # Initialize any cells that are None
        for c_idx in range(len(r)):
            if r[c_idx] is None:
                r[c_idx] = ""
        # Pad to col_count
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

        # Build a set of ALL cells that are part of merge ranges (including top-left)
        # These will be handled by merge_range, not written individually
        merged_cells = set()
        for r1, c1, r2, c2, val in merges:
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    merged_cells.add((r, c))

        # Write cells (skip ALL cells that are part of merge ranges)
        # merge_range will handle writing merged cells
        for r, row in enumerate(grid):
            for c, val in enumerate(row):
                if (r, c) in merged_cells:
                    continue  # Skip all cells that will be merged
                # Heuristic: first row as header if <th> used in HTML; if not sure, just use cell_fmt for all
                fmt = cell_fmt
                if r == 0:  # treat first row as header for simplicity
                    fmt = header_fmt
                worksheet.write(r, c, val, fmt)

        # Apply merges (XlsxWriter uses inclusive ranges, 0-based)
        # merge_range will write the value and format to the merged range
        max_row = len(grid) - 1
        max_col = len(grid[0]) - 1 if grid else 0
        for r1, c1, r2, c2, val in merges:
            # Clamp merge range to actual grid bounds (safety check)
            r2 = min(r2, max_row)
            c2 = min(c2, max_col)
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
            <!-- Week 1 -->
            <tr>
            <td rowspan="5">1</td>
            <td rowspan="5">3 posts, 2 stories; Post times 11am, 6pm</td>
            <td>Post</td>
            <td>01-Nov-2025</td>
                <td>Welcome to Patron's Day!</td>
                <td>Kickstart engagement; introduce event vibe</td>
                <td>Vibrant visuals of the campus, student groups & iconic spots with a welcoming message for the Patron's Day celebration.</td>
                <td>Use Canva templates; Tag Student Ambassadors.</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>03-Nov-2025</td>
                <td>Countdown Begins</td>
                <td>Build excitement for Patron's Day</td>
                <td>Post a countdown graphic highlighting days left until the event.</td>
                <td>Add countdown sticker; Share event details.</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>05-Nov-2025</td>
                <td>Behind the Scenes</td>
                <td>Engage audience with event preparations</td>
                <td>Share behind-the-scenes content of the event setup and team preparations.</td>
                <td>Use BTS stickers; Tag organizing committee.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>02-Nov-2025</td>
                <td>Excitement Polls</td>
                <td>Gather insights on what students expect</td>
                <td>Poll: "What are you most excited for about Patron's Day?" with interactive responses.</td>
                <td>Use campus GIF stickers; Share results in follow-up story.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>04-Nov-2025</td>
                <td>Campus Culture Highlights</td>
                <td>Increase relatability and showcase vibrant culture</td>
                <td>Share snippets of vibrant campus life leading up to Patron's Day.</td>
                <td>Tag students; Use event-themed stickers.</td>
            </tr>

            <!-- Week 2 -->
            <tr>
            <td rowspan="8">2</td>
            <td rowspan="8">3 posts, 5 stories; Post times 12pm, 7pm</td>
            <td>Post</td>
            <td>07-Nov-2025</td>
                <td>Festival Hype</td>
                <td>Boost anticipation for the upcoming festival</td>
                <td>Teaser visuals highlighting festival themes with a colorful layout.</td>
                <td>Add countdown sticker; Include CTA to RSVP.</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>09-Nov-2025</td>
                <td>Meet Our Performers</td>
                <td>Engage audience with performer previews</td>
                <td>Spotlight profiles of performers set to feature at Patron's Day.</td>
                <td>Include teaser video clips; Tag performers.</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>11-Nov-2025</td>
                <td>Throwback to Past Events</td>
                <td>Use nostalgia to encourage RSVPs</td>
                <td>Post a collage or video montage from previous Patron's Day highlights.</td>
                <td>Encourage RSVPs; Use highlights from past events.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>08-Nov-2025</td>
            <td>Behind the Scenes</td>
            <td>Provide insider access to drive engagement</td>
                <td>Share clips from event setup and interviews with organizers.</td>
                <td>Tag organizing committee; Use fun BTS stickers.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>10-Nov-2025</td>
            <td>Event Voices</td>
            <td>Increase participation by spotlighting student opinions</td>
                <td>Quick vox pops on favorite past events!</td>
                <td>Include Swipe-up link for RSVP.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>12-Nov-2025</td>
                <td>Countdown to Patron's Day</td>
                <td>Build excitement closer to the event</td>
                <td>Share daily countdown with visuals of event preparation.</td>
                <td>Use engagement stickers; Include event highlights.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>13-Nov-2025</td>
                <td>Guess the Performer</td>
                <td>Gamify engagement with curiosity hooks</td>
                <td>Trivia: Guess who’s performing?</td>
                <td>Reveal tomorrow; Use interactive stickers.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>14-Nov-2025</td>
                <td>Festival Sneak Peek</td>
                <td>Generate buzz for the event</td>
                <td>Share a sneak peek of festival decorations and layout.</td>
                <td>Tag event team; Use fun stickers.</td>
            </tr>

            <!-- Week 3 -->
            <tr>
            <td rowspan="9">3</td>
            <td rowspan="9">3 posts, 6 stories; Post times 11am, 5pm</td>
            <td>Post</td>
            <td>15-Nov-2025</td>
                <td>Student Stories</td>
                <td>Empower student voices & creativity</td>
                <td>Feature standout student works leading up to the event.</td>
                <td>Include submission CTA; Tag featured students.</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>17-Nov-2025</td>
                <td>Creative Showcase</td>
                <td>Highlight diversity of student talent</td>
                <td>Showcase a carousel of student art/design highlights.</td>
                <td>Tag creators; Encourage shares.</td>
            </tr>
            <tr>
            <td>Post</td>
            <td>19-Nov-2025</td>
                <td>Creator Interviews</td>
            <td>Increase relatability through personal storytelling</td>
                <td>Feature short interviews with student creators.</td>
                <td>High-share value; Engage audience in comments.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>16-Nov-2025</td>
                <td>Creative Journey</td>
                <td>Humanize creations and inspire participation</td>
                <td>Behind-the-scenes of creators preparing for the event.</td>
                <td>Tag participants; Use engaging stickers.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>18-Nov-2025</td>
            <td>Live Feature Voting</td>
            <td>Boost real-time participation and feedback</td>
                <td>Prompt live voting for features; Engage audience.</td>
                <td>Use engagement stickers; Encourage reposts.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>20-Nov-2025</td>
                <td>Student Showcase Highlights</td>
                <td>Sustain momentum around creative submissions</td>
                <td>Slideshow of student entries leading to the event.</td>
                <td>Include CTA to vote/share; Engage audience.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>21-Nov-2025</td>
                <td>Creator Introductions</td>
                <td>Help audience connect with featured students</td>
                <td>Mini interviews with selected student creators.</td>
                <td>Add handle mentions; Use creative stickers.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>22-Nov-2025</td>
                <td>Showcase Countdown</td>
                <td>Build hype toward final reveal</td>
                <td>Countdown to final showcase post with visuals.</td>
                <td>Build excitement; Use event-themed stickers.</td>
            </tr>
            <tr>
            <td>Story</td>
            <td>23-Nov-2025</td>
                <td>Patron's Day Teaser</td>
                <td>Generate buzz for the event</td>
                <td>Share teaser visuals of performances and activities planned for Patron's Day.</td>
                <td>Use event hashtags; Tag performers.</td>
            </tr>
            
            <!-- Week 4 -->
            <tr>
                <td rowspan="11">4</td>
                <td rowspan="11">Daily posts leading up to the event, multiple stories</td>
                <td>Post</td>
                <td>01-Feb-2026</td>
                <td>Event Kickoff!</td>
                <td>Drive engagement and excitement for the event</td>
                <td>Highlight major attractions, schedule, and invite alumni and the public to participate.</td>
                <td>Use event graphics; Tag all partners involved.</td>
            </tr>
            <tr>
                <td>Post</td>
                <td>02-Feb-2026</td>
                <td>Featured Performers</td>
                <td>Engage audience with performer spotlights</td>
                <td>Detailed posts about featured performers with clips and bios.</td>
                <td>Tag performers; Include countdown to their performances.</td>
            </tr>
            <tr>
                <td>Post</td>
                <td>03-Feb-2026</td>
                <td>Festival Activities Schedule</td>
                <td>Provide detailed event schedule for participants</td>
                <td>Share a graphic with the entire event schedule and activities planned.</td>
                <td>Include RSVP CTA; Use engaging visuals.</td>
            </tr>
            <tr>
                <td>Post</td>
                <td>04-Feb-2026</td>
                <td>Community Engagement</td>
                <td>Highlight local partnerships</td>
                <td>Showcase local businesses and partners supporting the event.</td>
                <td>Tag partners; Use community-focused hashtags.</td>
            </tr>
            <tr>
                <td>Post</td>
                <td>05-Feb-2026</td>
                <td>Live Updates</td>
                <td>Keep audience engaged during the event</td>
                <td>Share live updates and highlights during the festival.</td>
                <td>Use event hashtags; Engage audience in comments.</td>
            </tr>
            <tr>
                <td>Story</td>
                <td>01-Feb-2026</td>
                <td>Behind the Scenes</td>
                <td>Show real-time event setup</td>
                <td>Share clips from event setup and interviews with organizers.</td>
                <td>Tag event team; Use fun BTS stickers.</td>
            </tr>
            <tr>
                <td>Story</td>
                <td>02-Feb-2026</td>
                <td>Live Vote for Best Moments</td>
                <td>Engage audience in real-time</td>
                <td>Ask followers to vote for their favorite moments as they happen.</td>
                <td>Use polls and engagement stickers; Encourage interaction.</td>
            </tr>
            <tr>
                <td>Story</td>
                <td>03-Feb-2026</td>
                <td>Patron's Day Recap</td>
                <td>Summarize the best moments</td>
                <td>Share highlights of the event and thank participants.</td>
                <td>Use recap stickers; Tag participants.</td>
            </tr>
            <tr>
                <td>Story</td>
                <td>04-Feb-2026</td>
                <td>Community Shoutout</td>
                <td>Thank local partners and participants</td>
                <td>Give shoutouts to everyone who made the event successful.</td>
                <td>Tag partners; Use appreciation stickers.</td>
            </tr>
            <tr>
                <td>Story</td>
                <td>05-Feb-2026</td>
                <td>Post-Event Engagement</td>
                <td>Encourage ongoing community interaction</td>
                <td>Invite followers to share their experiences and tag the page.</td>
                <td>Use CTA to share stories; Encourage use of event hashtags.</td>
            </tr>
        </tbody>
        </table>
    """
    print(html_to_excel_tool.func(html_str=html_str))