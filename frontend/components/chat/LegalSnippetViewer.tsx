import React from "react";
import { FileText, Bookmark, Info, CheckCircle2, Scale } from "lucide-react";

/**
 * Làm sạch các lỗi chính tả, font chữ, OCR ligatures tiếng Việt
 * và rác bảng biểu thường gặp trong văn bản TTHC / đất đai (QĐ 1467, QĐ 1085, Luật Đất đai)
 */
export function cleanLegalText(raw: string): string {
  if (!raw) return "";

  let text = raw;

  // 0. Sửa các lỗi OCR đặc thù do quét bảng ngang dòng trong QĐ 1467 (Quy trình nội bộ)
  text = text.replace(
    /gửi người sử dụng\s+Văn phòng Đăng [^\n]*\s*Bước\s*2\s*đất để bổ sung hoàn chỉnh;?\s*Đất đai\/Chi nhánh Văn làm việc/gi,
    "gửi người sử dụng đất để bổ sung hoàn chỉnh.\n- Cơ quan thực hiện: Văn phòng Đăng ký Đất đai / Chi nhánh Văn phòng Đăng ký Đất đai (02 ngày làm việc)"
  );
  text = text.replace(
    /Cập nhật cơ sở dữ liệu đất [^\n]*\|\s*Phòng Đăng ký Đất đai\s*\n\s*lập hồ sơ để Nhà nước quản lý\.\s*\n\s*phòng Đăng ký Đất đai làm việc/gi,
    "Cập nhật cơ sở dữ liệu đất đai và lập hồ sơ để Nhà nước quản lý.\n- Cơ quan thực hiện: Văn phòng Đăng ký Đất đai / Chi nhánh Văn phòng Đăng ký Đất đai"
  );
  text = text.replace(
    /Xác nhận\s*iãy chứng nhận đã cấp\s+Văn phòng Đăng ký\s+0[\.,]5\s*ngà\s*\n\s*Bước\s*4\s*\|\s*hoặc in giấy chứng nhận[^\n]*/gi,
    "Bước 4: Xác nhận Giấy chứng nhận đã cấp hoặc in Giấy chứng nhận.\n- Cơ quan thực hiện: Văn phòng Đăng ký Đất đai / Chi nhánh Văn phòng Đăng ký Đất đai (0,5 ngày làm việc)"
  );

  // 1. Khắc phục các lỗi dính chữ (ligature) và lỗi font OCR tiếng Việt
  text = text
    .replace(/[&§]\s*Ễy\s*đủ/gi, "đầy đủ")
    .replace(/&Ễy/gi, "đầy")
    .replace(/\bỄy\s*đủ/gi, "đầy đủ")
    .replace(/chưa\s*&[^\s]+\s*đủ/gi, "chưa đầy đủ")
    .replace(/(?<=[a-zà-ỹA-ZÀ-Ỹ])iãy/gi, " Giấy")
    .replace(/iãy\s*chứng\s*nhận/gi, "Giấy chứng nhận")
    .replace(/\biãy\b/gi, "giấy")
    .replace(/\bgiãy\b/gi, "giấy")
    .replace(/Đăng\s*Ối\b/g, "Đăng ký")
    .replace(/Đăng\s*ối\b/g, "Đăng ký")
    .replace(/0[\.,]5\s*ngà\b/gi, "0,5 ngày")
    .replace(/\bngà\s+làm\s*việc/gi, "ngày làm việc")
    .replace(/\bđất\s*đi\s*và\b/gi, "đất đai và")
    .replace(/\bdất\s*đai\b/gi, "đất đai")
    .replace(/\bdât\s*dai\b/gi, "đất đai")
    .replace(/\bthửa\s*đắt\b/gi, "thửa đất")
    .replace(/Cấp\s*đồi/gi, "Cấp đổi")
    .replace(/gắn\s*liên\b/gi, "gắn liền")
    .replace(/Nghị\s*định\s*sô\b/gi, "Nghị định số")
    .replace(/yêu\s*câu\b/gi, "yêu cầu")
    .replace(/ghi\s*đây\s*đủ\b/gi, "ghi đầy đủ")
    .replace(/quyen\s*sử\s*dung\b/gi, "quyền sử dụng")
    .replace(/tải\s*sản\b/gi, "tài sản")
    .replace(/đo\s*đạc\s*đề\b/gi, "đo đạc để")
    .replace(/ffl[l1íiìỉĩị]*t\s*đai/gi, "đất đai")
    .replace(/ffl[l1íiìỉĩị]*t/gi, "đất")
    .replace(/đất\s*ffl[l1íiìỉĩị]*t/gi, "đất đai")
    .replace(/quyền\s*sử\s*dụng\s*ffl[l1íiìỉĩị]*t/gi, "quyền sử dụng đất")
    .replace(/thủ\s*tục\s*ffl[l1íiìỉĩị]*t/gi, "thủ tục đất")
    .replace(/fflấy/gi, "giấy")
    .replace(/[øo][1la]\s*đình/gi, "gia đình")
    .replace(/[øo][1la]/gi, "gia")
    .replace(/cơ\s*quan\s*có\s*thẩm\s*quy[êe]n/gi, "cơ quan có thẩm quyền")
    .replace(/s[ồổ]\s*đ[ỏo]/gi, "sổ đỏ")
    .replace(/sổ\s*đ[ồổ]/gi, "sổ đỏ")
    .replace(/giấy\s*chứng\s*nhận\s*quy[êe]n/gi, "giấy chứng nhận quyền");

  // 2. Dọn dẹp rác ký tự bảng biểu OCR, dấu pipe, backslash thừa
  text = text
    .replace(/[,;]?\s*\bm\s*[:;,]\s*/g, ", ")
    .replace(/\|\s*[,;]?\s*\??\s*[A-ZĐ0-9_]{2,8}\b/g, "")
    .replace(/\|\s*[,;?\s]+(?=\n|$)/g, "")
    .replace(/^[ \t]*[\\\/][ \t]*/gm, "")
    .replace(/\bBước\s*(\d+)\s*[:\-|]?\s*/gi, "\nBước $1: ")
    .replace(/\s*\|\s*/g, " - ")
    .replace(/[,;][,\s;]+/g, ", ");

  // 3. Chuẩn hóa khoảng trắng
  text = text.replace(/[ \t]+/g, " ");

  // 4. Lọc bỏ các dòng rác OCR và các từ mồ côi
  const rawLines = text.split("\n");
  const filteredLines: string[] = [];

  for (let i = 0; i < rawLines.length; i++) {
    const trimmed = rawLines[i].trim();
    // Bỏ qua dòng rác OCR
    if (
      trimmed === "lời" ||
      trimmed === "lði" ||
      trimmed === "lòi" ||
      trimmed === "lơi" ||
      /^[0-9]+$/.test(trimmed) ||
      /^trang\s+[0-9]+$/i.test(trimmed) ||
      /^[,\.;:\|\/\\?!\s-]+$/.test(trimmed)
    ) {
      continue;
    }
    // Bỏ qua từ mồ côi 1-2 từ ở dòng đầu tiên nếu không phải tiêu đề
    if (
      filteredLines.length === 0 &&
      trimmed.split(" ").length <= 2 &&
      !trimmed.startsWith("Điều") &&
      !trimmed.startsWith("Mục") &&
      !trimmed.startsWith("Bước") &&
      !trimmed.startsWith("[") &&
      !trimmed.startsWith("(")
    ) {
      continue;
    }
    filteredLines.push(trimmed);
  }

  // 5. Ghép các dòng bị gãy giữa chừng (dòng kết thúc bằng dấu phẩy, và, hoặc, -)
  const merged: string[] = [];
  for (const line of filteredLines) {
    if (line.startsWith("Bước ")) {
      merged.push(line);
    } else if (
      merged.length > 0 &&
      (merged[merged.length - 1].endsWith(",") ||
        merged[merged.length - 1].endsWith(";") ||
        merged[merged.length - 1].endsWith(" -") ||
        merged[merged.length - 1].endsWith(" và") ||
        merged[merged.length - 1].endsWith(" hoặc") ||
        !/[\.\?!:]$/.test(merged[merged.length - 1])) &&
      !line.startsWith("-") &&
      !line.startsWith("+") &&
      !line.startsWith("•") &&
      !line.startsWith("Bước") &&
      !line.startsWith("Điều") &&
      !line.startsWith("(") &&
      !line.startsWith("[")
    ) {
      merged[merged.length - 1] = merged[merged.length - 1] + " " + line;
    } else {
      merged.push(line);
    }
  }

  return merged.join("\n\n").replace(/\n{3,}/g, "\n\n");
}

/**
 * Tự động in đậm và tô sáng các cụm từ pháp lý quan trọng:
 * Số hiệu văn bản, tên biểu mẫu, tên loại giấy tờ pháp lý
 */
function highlightLegalTerms(text: string): React.ReactNode[] {
  // Regex bắt các từ ngữ pháp quy then chốt
  const pattern = /(Nghị định số\s+[0-9]+(?:\/[0-9]+)?\/NĐ-CP|Thông tư số\s+[0-9]+(?:\/[0-9]+)?\/TT-[A-Z0-9]+|Luật Đất đai(?:\s+năm\s+[0-9]{4}|\s+[0-9]{4})?|Mẫu số\s+[0-9]+[A-Za-z0-9\/-]*|Đơn đăng ký biến động đất đai[^\n,;.]*|Giấy chứng nhận đã cấp|Giấy chứng nhận quyền sử dụng đất[^\n,;.]*|Chi nhánh Văn phòng đăng ký đất đai|Bộ phận Một cửa|Ủy ban nhân dân[^\n,;.]*)/gi;

  const parts = text.split(pattern);
  return parts.map((part, index) => {
    if (!part) return null;
    if (pattern.test(part)) {
      return (
        <strong
          key={index}
          style={{
            color: "#0f172a",
            fontWeight: 700,
            background: "rgba(22, 107, 69, 0.08)",
            padding: "1px 4px",
            borderRadius: "4px",
          }}
        >
          {part}
        </strong>
      );
    }
    return <span key={index}>{part}</span>;
  });
}

interface LegalSnippetViewerProps {
  rawText: string;
}

export default function LegalSnippetViewer({ rawText }: LegalSnippetViewerProps) {
  if (!rawText || !rawText.trim()) {
    return (
      <div style={{ padding: "16px", color: "#64748b", fontStyle: "italic", textAlign: "center" }}>
        Không có đoạn trích chi tiết cho nguồn này.
      </div>
    );
  }

  const cleaned = cleanLegalText(rawText);
  const lines = cleaned.split("\n");

  let procedureTitle = "";
  let sectionTitle = "";
  const bodyParagraphs: {
    type: "heading" | "step" | "subheading" | "agency_time" | "item" | "case_note" | "text";
    content: string;
  }[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    // Bóc tách [Thủ tục: ...]
    const procMatch = line.match(/^\[Thủ tục:\s*(.*?)\]$/i);
    if (procMatch) {
      procedureTitle = procMatch[1].trim();
      continue;
    }

    // Bóc tách [Mục: ...]
    const secMatch = line.match(/^\[Mục:\s*(.*?)\]$/i);
    if (secMatch) {
      sectionTitle = secMatch[1].trim();
      continue;
    }

    // Tiêu đề mục ví dụ "(3) Thành phần, số lượng hồ sơ", "Điều 1...", "1. Trình tự thực hiện"
    if (/^\([0-9]+\)\s+/i.test(line) || /^Điều\s+[0-9]+/i.test(line) || /^[0-9]+\.\s+[A-ZĐ]/i.test(line)) {
      bodyParagraphs.push({ type: "heading", content: line });
      continue;
    }

    // Các Bước quy trình hành chính (Bước 1:, Bước 2...)
    if (/^Bước\s+[0-9]+/i.test(line)) {
      bodyParagraphs.push({ type: "step", content: line });
      continue;
    }

    // Cơ quan thực hiện / Thời hạn giải quyết
    if (/^-\s*(Cơ quan thực hiện|Thời hạn|Địa điểm tiếp nhận)/i.test(line)) {
      bodyParagraphs.push({ type: "agency_time", content: line.replace(/^-\s*/, "") });
      continue;
    }

    // Tiêu đề phụ như "- Thành phần hồ sơ:" hoặc "- Số lượng hồ sơ:"
    if (/^-\s*(Thành phần|Số lượng|Trình tự|Cách thức|Cơ quan|Yêu cầu|Điều kiện|Hồ sơ)/i.test(line)) {
      bodyParagraphs.push({ type: "subheading", content: line.replace(/^-\s*/, "") });
      continue;
    }

    // Các mục danh sách hồ sơ / giấy tờ (+ Đơn..., + Giấy..., • ...)
    if (line.startsWith("+") || line.startsWith("•") || line.startsWith("- ")) {
      const cleanItem = line.replace(/^[+•\-]\s*/, "");
      bodyParagraphs.push({ type: "item", content: cleanItem });
      continue;
    }

    // Các đoạn điều kiện, trường hợp cụ thể, lưu ý ("Trường hợp...", "Lưu ý...", "Đối với...")
    if (/^(Trường hợp|Lưu ý|Đối với|Người sử dụng đất|Cơ quan tiếp nhận)\b/i.test(line)) {
      bodyParagraphs.push({ type: "case_note", content: line });
      continue;
    }

    // Đoạn văn thông thường
    bodyParagraphs.push({ type: "text", content: line });
  }

  return (
    <div
      style={{
        fontFamily: "'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
        color: "#1e293b",
        fontSize: "13.5px",
        lineHeight: 1.75,
      }}
    >
      {/* 1. Header Card: Tên Thủ tục Hành chính & Mục pháp lý */}
      {(procedureTitle || sectionTitle) && (
        <div
          style={{
            background: "linear-gradient(135deg, #f0fdf4 0%, #ecfdf5 100%)",
            border: "1px solid #bbf7d0",
            borderRadius: "10px",
            padding: "12px 16px",
            marginBottom: "16px",
            boxShadow: "0 1px 3px rgba(22, 107, 69, 0.05)",
          }}
        >
          {procedureTitle && (
            <div style={{ display: "flex", alignItems: "flex-start", gap: "10px", marginBottom: sectionTitle ? "6px" : "0" }}>
              <Bookmark size={17} style={{ color: "#166b45", flexShrink: 0, marginTop: "2px" }} />
              <div>
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: 700,
                    color: "#15803d",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}
                >
                  Thủ tục hành chính
                </span>
                <div style={{ fontWeight: 700, fontSize: "14px", color: "#0f172a", marginTop: "1px", lineHeight: 1.4 }}>
                  {procedureTitle}
                </div>
              </div>
            </div>
          )}

          {sectionTitle && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                marginTop: procedureTitle ? "4px" : "0",
                padding: "3px 10px",
                background: "#ffffff",
                border: "1px solid #cbd5e1",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                color: "#334155",
              }}
            >
              <Info size={13} style={{ color: "#0284c7" }} />
              <span>{sectionTitle}</span>
            </div>
          )}
        </div>
      )}

      {/* 2. Nội dung đoạn trích quy định pháp luật chuẩn văn bản */}
      <div
        style={{
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: "10px",
          padding: "18px 20px",
          boxShadow: "inset 0 1px 2px rgba(0,0,0,0.02)",
        }}
      >
        {bodyParagraphs.map((para, idx) => {
          // Tiêu đề đề mục: (3) Thành phần, số lượng hồ sơ
          if (para.type === "heading") {
            return (
              <div
                key={idx}
                style={{
                  fontSize: "14.5px",
                  fontWeight: 800,
                  color: "#166b45",
                  paddingBottom: "8px",
                  marginBottom: "12px",
                  marginTop: idx > 0 ? "16px" : "0",
                  borderBottom: "2px solid #dcfce7",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  letterSpacing: "-0.01em",
                }}
              >
                <Scale size={16} style={{ color: "#166b45", flexShrink: 0 }} />
                <span>{para.content}</span>
              </div>
            );
          }

          // Bước trong quy trình hành chính (Bước 1, Bước 2, Bước 4...)
          if (para.type === "step") {
            const stepMatch = para.content.match(/^(Bước\s+[0-9]+(?:\.[0-9]+)?):?\s*(.*)/i);
            const badge = stepMatch ? stepMatch[1] : "Bước";
            const rest = stepMatch ? stepMatch[2] : para.content;
            return (
              <div
                key={idx}
                style={{
                  marginTop: idx > 0 ? "14px" : "6px",
                  marginBottom: "10px",
                  padding: "12px 14px",
                  background: "#f0fdf4",
                  border: "1px solid #bbf7d0",
                  borderRadius: "8px",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  boxShadow: "0 1px 2px rgba(22, 107, 69, 0.04)",
                }}
              >
                <span
                  style={{
                    background: "#166b45",
                    color: "#ffffff",
                    fontSize: "12px",
                    fontWeight: 700,
                    padding: "3px 8px",
                    borderRadius: "6px",
                    flexShrink: 0,
                    marginTop: "1px",
                    letterSpacing: "0.3px",
                  }}
                >
                  {badge}
                </span>
                <div style={{ flex: 1, fontSize: "13.5px", lineHeight: 1.68, color: "#0f172a" }}>
                  {highlightLegalTerms(rest)}
                </div>
              </div>
            );
          }

          // Cơ quan thực hiện / Thời hạn giải quyết
          if (para.type === "agency_time") {
            return (
              <div
                key={idx}
                style={{
                  margin: "6px 0 10px 12px",
                  padding: "8px 12px",
                  background: "#f8fafc",
                  borderLeft: "3.5px solid #0284c7",
                  borderRadius: "0 6px 6px 0",
                  fontSize: "12.5px",
                  color: "#334155",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                }}
              >
                <Info size={14} style={{ color: "#0284c7", flexShrink: 0 }} />
                <span>{highlightLegalTerms(para.content)}</span>
              </div>
            );
          }

          // Tiêu đề phụ: Thành phần hồ sơ / Số lượng hồ sơ
          if (para.type === "subheading") {
            return (
              <div
                key={idx}
                style={{
                  fontSize: "13.5px",
                  fontWeight: 700,
                  color: "#0f172a",
                  marginTop: "14px",
                  marginBottom: "8px",
                  textTransform: "uppercase",
                  letterSpacing: "0.4px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                }}
              >
                <span
                  style={{
                    width: "4px",
                    height: "14px",
                    background: "#166b45",
                    borderRadius: "2px",
                    display: "inline-block",
                  }}
                />
                <span>{para.content}</span>
              </div>
            );
          }

          // Từng thành phần giấy tờ (+ Đơn..., + Giấy...)
          if (para.type === "item") {
            return (
              <div
                key={idx}
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  padding: "9px 12px",
                  marginLeft: "4px",
                  marginBottom: "8px",
                  background: "#f8fafc",
                  borderRadius: "8px",
                  border: "1px solid #f1f5f9",
                  textAlign: "justify",
                }}
              >
                <CheckCircle2
                  size={15}
                  style={{ color: "#16a34a", flexShrink: 0, marginTop: "4px" }}
                />
                <div style={{ flex: 1, lineHeight: 1.68, color: "#1e293b" }}>
                  {highlightLegalTerms(para.content)}
                </div>
              </div>
            );
          }

          // Đoạn quy định chi tiết: Trường hợp..., Lưu ý...
          if (para.type === "case_note") {
            return (
              <div
                key={idx}
                style={{
                  margin: "12px 0 12px 14px",
                  padding: "11px 15px",
                  borderLeft: "3.5px solid #0284c7",
                  background: "#f0f9ff",
                  borderRadius: "0 8px 8px 0",
                  fontSize: "13px",
                  fontStyle: "italic",
                  lineHeight: 1.72,
                  color: "#0369a1",
                  textAlign: "justify",
                }}
              >
                <strong style={{ fontStyle: "normal", color: "#075985" }}>Quy định chi tiết: </strong>
                {highlightLegalTerms(para.content)}
              </div>
            );
          }

          // Đoạn văn thông thường
          return (
            <p
              key={idx}
              style={{
                margin: "0 0 10px 0",
                textIndent: "20px",
                textAlign: "justify",
                lineHeight: 1.78,
                color: "#334155",
              }}
            >
              {highlightLegalTerms(para.content)}
            </p>
          );
        })}
      </div>
    </div>
  );
}
