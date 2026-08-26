"""
Patch DOCX templates:
- For <mc:AlternateContent> with wps:wsp (modern OOXML shapes, used by 2f2f/93c4):
  * Remove white solidFill → noFill (make transparent)
  * Inject mst_N_I jinja tag into wps:txbx/w:txbxContent
  * Also patch Fallback v:rect for compatibility
  
- For naked <v:rect> (used by 5de8/7c42/b741):
  * Set filled=f
  * Inject mst_N_I jinja tag into v:textbox/w:txbxContent
"""
import zipfile, glob, re, os


def patch_docx(path, out_path):
    """Patch one DOCX file. Returns count of patched squares."""
    state = {'count': 0}

    # ---- helper: build a centered w:p with the jinja tag ----
    def make_text_para(group, idx):
        return (
            f'<w:p><w:pPr><w:jc w:val="center"/>'
            f'<w:spacing w:before="0" w:after="0"/></w:pPr>'
            f'<w:r><w:rPr><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr>'
            f'<w:t>{{{{ mst_{group}_{idx} }}}}</w:t></w:r></w:p>'
        )

    def next_slot():
        count = state['count']
        group = (count // 13) + 1
        idx   = count % 13
        state['count'] += 1
        return group, idx

    def patch_wps_alt(m):
        """Handle <mc:AlternateContent> blocks containing wps:wsp shapes."""
        alt = m.group(0)

        # MST digit squares: 17.35pt (cx=220345 EMU)
        is_mst_square = '17.35pt' in alt or 'cx="220345"' in alt or 'cx="220' in alt
        # Checkbox squares: ~11.3pt (cx=144145 EMU) — just need noFill, no text injection
        is_checkbox = 'cx="144145"' in alt

        if not is_mst_square and not is_checkbox:
            return alt

        if is_mst_square:
            group, idx = next_slot()
            text_para = make_text_para(group, idx)

        # 1. In mc:Choice: make shape transparent (+ inject text for MST only)
        def patch_choice(cm):
            c = cm.group(0)
            # Remove white fill → noFill (for all shape types)
            c = re.sub(r'<a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>', '<a:noFill/>', c)
            if is_mst_square:
                # Inject digit jinja tag into txbxContent
                c = re.sub(
                    r'<w:txbxContent>.*?</w:txbxContent>',
                    f'<w:txbxContent>{text_para}</w:txbxContent>',
                    c, flags=re.DOTALL
                )
            return c

        alt = re.sub(r'<mc:Choice.*?</mc:Choice>', patch_choice, alt, flags=re.DOTALL)

        # 2. In mc:Fallback / v:rect: same treatment
        def patch_fallback_rect(rm):
            rect = rm.group(0)
            rect = re.sub(r'\bfillcolor="[^"]*"', '', rect)
            rect = re.sub(r'\bfilled="[^"]*"', '', rect)
            rect = rect.replace('<v:rect ', '<v:rect filled="f" ')
            if is_mst_square:
                rect = re.sub(
                    r'<w:txbxContent>.*?</w:txbxContent>',
                    f'<w:txbxContent>{text_para}</w:txbxContent>',
                    rect, flags=re.DOTALL
                )
            return rect

        alt = re.sub(r'<v:rect\b.*?</v:rect>', patch_fallback_rect, alt, flags=re.DOTALL)
        return alt


    def patch_naked_rect(m):
        """Handle naked <v:rect> elements (not inside mc:AlternateContent)."""
        rect = m.group(0)
        if '17.35pt' not in rect:
            return rect
        group, idx = next_slot()
        text_para = make_text_para(group, idx)
        rect = re.sub(r'\bfillcolor="[^"]*"', '', rect)
        rect = re.sub(r'\bfilled="[^"]*"', '', rect)
        rect = rect.replace('<v:rect ', '<v:rect filled="f" ')
        if '<v:textbox' in rect:
            rect = re.sub(
                r'<w:txbxContent>.*?</w:txbxContent>',
                f'<w:txbxContent>{text_para}</w:txbxContent>',
                rect, flags=re.DOTALL
            )
        else:
            rect = rect.replace(
                '</v:rect>',
                f'<v:textbox inset="0,0,0,0">'
                f'<w:txbxContent>{text_para}</w:txbxContent>'
                f'</v:textbox></v:rect>'
            )
        return rect

    with zipfile.ZipFile(path, 'r') as zin:
        with zipfile.ZipFile(out_path, 'w') as zout:
            for item in zin.infolist():
                content = zin.read(item.filename)
                if item.filename == 'word/document.xml':
                    xml = content.decode('utf-8')
                    # Process mc:AlternateContent blocks first
                    xml = re.sub(
                        r'<mc:AlternateContent>.*?</mc:AlternateContent>',
                        patch_wps_alt, xml, flags=re.DOTALL
                    )
                    # Then any remaining naked v:rect
                    xml = re.sub(
                        r'<v:rect\b.*?</v:rect>',
                        patch_naked_rect, xml, flags=re.DOTALL
                    )
                    content = xml.encode('utf-8')
                zout.writestr(item, content)
    return state['count']


for path in sorted(glob.glob('backend/data/templates/*.docx')):
    if path.endswith('.bak'):
        continue
    out_path = path + '.tmp'
    try:
        count = patch_docx(path, out_path)
        if count > 0:
            os.replace(out_path, path)
            print(f"OK Patched {count} squares in {os.path.basename(path)}")
        else:
            os.remove(out_path)
    except Exception as e:
        import traceback
        print(f"ERROR on {os.path.basename(path)}: {e}")
        traceback.print_exc()
        if os.path.exists(out_path):
            os.remove(out_path)

print("\nDone!")
