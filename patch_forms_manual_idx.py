with open("d:/TerraLegalAI/backend/app/api/v1/forms.py", "r", encoding="utf-8") as f:
    content = f.read()

old_manual_logic = """        # Xử lý các vùng vẽ tay (manual zones) có idx rất lớn (Date.now())
        pdf_path = os.path.join("data", "uploaded", f"{body.temp_id}_marked.pdf")
        if os.path.exists(pdf_path):
            import fitz
            doc = fitz.open(pdf_path)
            manual_additions = []
            for z in body.zones:
                try:
                    idx_val = int(z.get("idx", 0))
                    if idx_val > 1000000:  # Manual zone
                        p_num = z.get("page", 1) - 1
                        x, y, w, h = z.get("x", 0), z.get("y", 0), z.get("width", 0), z.get("height", 0)
                        if 0 <= p_num < len(doc):
                            page = doc[p_num]
                            # Lấy text bên trái (max 300px)
                            rect_left = fitz.Rect(max(0, x - 300), max(0, y - 10), x + w/2, y + h + 10)
                            text_left = page.get_textbox(rect_left).strip()
                            # Lấy text bên trên (max 50px)
                            rect_up = fitz.Rect(max(0, x - 20), max(0, y - 50), x + w + 20, y + h/2)
                            text_up = page.get_textbox(rect_up).strip()
                            
                            combined = f"{text_up} {text_left}".strip()
                            if combined:
                                # Tạo ngữ cảnh giả lập cho AI đoán
                                manual_additions.append(f"{combined} [[{idx_val}]]")
                except ValueError:
                    pass
            doc.close()
            
            if manual_additions:
                full_text += "\\n\\n--- CÁC VÙNG BỔ SUNG ---\\n" + "\\n".join(manual_additions)

        predictions = await asyncio.to_thread(_predict_labels, full_text)

        # Gắn predictions vào từng zone
        enriched_zones = []
        for z in body.zones:
            z_copy = dict(z)
            pred = predictions.get(str(z["idx"]))
            if pred:
                z_copy["suggested_label"] = pred["label"]
            enriched_zones.append(z_copy)"""

new_manual_logic = """        # Xử lý các vùng vẽ tay (manual zones) có idx rất lớn (Date.now())
        pdf_path = os.path.join("data", "uploaded", f"{body.temp_id}_marked.pdf")
        manual_mapping = {}
        m_idx = 9001
        
        if os.path.exists(pdf_path):
            import fitz
            doc = fitz.open(pdf_path)
            manual_additions = []
            for z in body.zones:
                try:
                    idx_val = int(z.get("idx", 0))
                    if idx_val > 1000000:  # Manual zone
                        manual_mapping[m_idx] = idx_val
                        mapped_idx = m_idx
                        m_idx += 1
                        
                        p_num = z.get("page", 1) - 1
                        x, y, w, h = z.get("x", 0), z.get("y", 0), z.get("width", 0), z.get("height", 0)
                        if 0 <= p_num < len(doc):
                            page = doc[p_num]
                            # Lấy text bên trái (max 300px)
                            rect_left = fitz.Rect(max(0, x - 300), max(0, y - 10), x + w/2, y + h + 10)
                            text_left = page.get_textbox(rect_left).strip()
                            # Lấy text bên trên (max 50px)
                            rect_up = fitz.Rect(max(0, x - 20), max(0, y - 50), x + w + 20, y + h/2)
                            text_up = page.get_textbox(rect_up).strip()
                            
                            combined = f"{text_up} {text_left}".strip()
                            if combined:
                                # Tạo ngữ cảnh giả lập cho AI đoán
                                manual_additions.append(f"{combined} [[{mapped_idx}]]")
                except ValueError:
                    pass
            doc.close()
            
            if manual_additions:
                full_text += "\\n\\n--- CÁC VÙNG BỔ SUNG ---\\n" + "\\n".join(manual_additions)

        predictions = await asyncio.to_thread(_predict_labels, full_text)

        # Gắn predictions vào từng zone
        enriched_zones = []
        for z in body.zones:
            z_copy = dict(z)
            idx_val = int(z["idx"])
            
            # Map back if it's a manual zone
            lookup_idx = idx_val
            for k, v in manual_mapping.items():
                if v == idx_val:
                    lookup_idx = k
                    break
                    
            pred = predictions.get(str(lookup_idx))
            if pred:
                z_copy["suggested_label"] = pred["label"]
            enriched_zones.append(z_copy)"""

if "manual_mapping" not in content:
    content = content.replace(old_manual_logic, new_manual_logic)

with open("d:/TerraLegalAI/backend/app/api/v1/forms.py", "w", encoding="utf-8") as f:
    f.write(content)
