"""Render the N1 essay to a site page.

Handles multi-line list items -- a continuation line (indented, or simply the
next non-blank line inside a list) belongs to the item above it, not to a new
paragraph. The first version split them and the flow read as fragments.
"""
import html, re, pathlib, sys

def inline(s):
    s = html.escape(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    return s

def convert(md):
    out, lines, i = [], md.split('\n'), 0
    BULLET = re.compile(r'^- +(.*)')
    NUMBER = re.compile(r'^\d+\.\s+(.*)')

    def gather(pat, tag):
        """Collect a list, folding continuation lines into the current item."""
        nonlocal i
        items = []
        while i < len(lines):
            m = pat.match(lines[i])
            if m:
                items.append(m.group(1).strip()); i += 1
            elif lines[i].strip() and not lines[i].lstrip().startswith(('#','|','---')) \
                 and not BULLET.match(lines[i]) and not NUMBER.match(lines[i]) and items:
                items[-1] += ' ' + lines[i].strip(); i += 1      # continuation
            else:
                break
        return f'<{tag}>' + ''.join(f'<li>{inline(x)}</li>' for x in items) + f'</{tag}>'

    while i < len(lines):
        l = lines[i]
        if l.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                rows.append(lines[i]); i += 1
            cells = lambda r: [c.strip() for c in r.strip('|').split('|')]
            head, body = cells(rows[0]), [cells(r) for r in rows[2:]]
            t = '<div class="tablewrap"><table><thead><tr>' + \
                ''.join(f'<th>{inline(c)}</th>' for c in head) + '</tr></thead><tbody>'
            for r in body:
                t += '<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in r) + '</tr>'
            out.append(t + '</tbody></table></div>'); continue
        if l.startswith('#'):
            n = len(l) - len(l.lstrip('#')); out.append(f'<h{n}>{inline(l[n:].strip())}</h{n}>'); i += 1; continue
        if l.strip() == '---':
            out.append('<hr>'); i += 1; continue
        if BULLET.match(l): out.append(gather(BULLET, 'ul')); continue
        if NUMBER.match(l): out.append(gather(NUMBER, 'ol')); continue
        if l.strip().startswith('*') and l.strip().endswith('*') and len(l.strip()) > 2 \
           and '**' not in l:
            out.append(f'<p class="coda">{inline(l.strip().strip("*"))}</p>'); i += 1; continue
        if l.strip():
            para = [l]; i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith(('#','|')) \
                  and lines[i].strip() != '---' and not BULLET.match(lines[i]) and not NUMBER.match(lines[i]):
                para.append(lines[i]); i += 1
            out.append(f'<p>{inline(" ".join(x.strip() for x in para))}</p>'); continue
        i += 1
    return '\n'.join(out)

CSS = open(sys.argv[2], encoding='utf-8').read() if len(sys.argv) > 2 else ''
md = open('essay/N1-ESSAY.md', encoding='utf-8').read()
print(convert(md))
