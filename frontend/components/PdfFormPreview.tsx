"use client";

import React, { useState, useEffect, useLayoutEffect, useRef, useCallback } from "react";

const configuredApiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
const apiOrigin = configuredApiUrl
  ? configuredApiUrl.replace(/\/api\/v1$/, "")
  : "http://localhost:8000";

function resolveApiAssetUrl(value: string): string {
  if (value.startsWith("data:") || value.startsWith("blob:")) return value;

  try {
    const parsed = new URL(value, `${apiOrigin}/`);
    if (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") {
      const target = new URL(apiOrigin);
      parsed.protocol = target.protocol;
      parsed.host = target.host;
    }
    return parsed.toString();
  } catch {
    return `${apiOrigin}${value.startsWith("/") ? "" : "/"}${value}`;
  }
}

interface Zone {
  idx: number;
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
  field_type?: string;
  suggested_label?: string;
  confidence?: number;
  section?: string;
}

interface TextBlock {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
}

type AiPred = { label: string; description: string; confidence: number; section: string };
type PreviewMode = 'label' | 'add' | 'adjust' | 'remove' | 'merge';

interface PdfFormPreviewProps {
  pageImages: string[];
  zones: Zone[];
  textBlocks?: TextBlock[];
  mode: PreviewMode;
  labeledZones: Record<string, string>;
  mergeSelection: Set<string>;
  activeZoneIdx?: string | null;
  onZoneClick: (zoneIdx: number) => void;
  onTextBlockClick?: (text: string) => void;
  onZonesChange?: (newZones: Zone[]) => void;
  readOnly?: boolean;
  aiPredictions?: Record<string, AiPred>;
  fieldDetails?: Record<string, { num: number; label: string }>;
  pageDimensions?: { page: number; width: number; height: number }[];
}

export default function PdfFormPreview({
  pageImages,
  zones,
  mode,
  labeledZones,
  mergeSelection,
  activeZoneIdx,
  onZoneClick,
  onTextBlockClick,
  onZonesChange,
  readOnly,
  aiPredictions = {},
  fieldDetails = {},
  textBlocks = [],
  pageDimensions,
}: PdfFormPreviewProps) {
  // Keep a stable design scale. The old ResizeObserver squeezed the document to
  // the panel width, which made small fields difficult to select. Overflow now
  // scrolls horizontally instead of changing the document coordinates/scale.
  const [zoom, setZoom] = useState(1);
  // DOCX preview pages are rendered at roughly 150 DPI (A4 ≈ 1,200 px wide).
  // Using 800 px as "100%" still visually compressed the original document.
  const DESIGN_PAGE_WIDTH = 1200;
  const pageWidth = Math.round(DESIGN_PAGE_WIDTH * zoom);
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollTopRef = useRef<number>(0);

  // Lưu vị trí cuộn trước khi zones thay đổi
  useLayoutEffect(() => {
    return () => {
      if (containerRef.current) {
        scrollTopRef.current = containerRef.current.scrollTop;
      }
    };
  });

  // Khôi phục vị trí cuộn sau khi zones thay đổi (chỉ khi thực sự thay đổi)
  useLayoutEffect(() => {
    if (containerRef.current && scrollTopRef.current > 0) {
      containerRef.current.scrollTop = scrollTopRef.current;
    }
  }, [zones]);

  const token = typeof window !== 'undefined'
    ? (localStorage.getItem("terralegal_access_token") ?? sessionStorage.getItem("terralegal_access_token"))
    : null;

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%", height: "100%", overflow: "auto",
        background: "#e2e8f0",
        position: "absolute", top: 0, left: 0, right: 0, bottom: 0,
        overflowAnchor: "none" // Prevent browser scroll jumps
      }}
    >
      <div style={{
        position: "sticky", top: 10, left: 0, zIndex: 30,
        width: "fit-content", margin: "0 auto -38px", height: 38,
        display: "flex", alignItems: "center", gap: 4,
        padding: "4px 6px", borderRadius: 8,
        background: "rgba(15, 23, 42, 0.88)", color: "#fff",
        boxShadow: "0 3px 10px rgba(0,0,0,0.22)", backdropFilter: "blur(4px)"
      }}>
        <button
          type="button"
          onClick={() => setZoom(value => Math.max(0.5, Number((value - 0.25).toFixed(2))))}
          disabled={zoom <= 0.5}
          title="Thu nhỏ"
          style={{ width: 28, height: 28, border: 0, borderRadius: 5, background: "rgba(255,255,255,0.12)", color: "#fff", cursor: zoom <= 0.5 ? "not-allowed" : "pointer", fontSize: 18 }}
        >−</button>
        <button
          type="button"
          onClick={() => setZoom(1)}
          title="Về kích thước tài liệu 100% (1.200 px)"
          style={{ minWidth: 58, height: 28, border: 0, borderRadius: 5, background: zoom === 1 ? "#2563eb" : "rgba(255,255,255,0.12)", color: "#fff", cursor: "pointer", fontSize: 12, fontWeight: 700 }}
        >{Math.round(zoom * 100)}%</button>
        <button
          type="button"
          onClick={() => setZoom(value => Math.min(2, Number((value + 0.25).toFixed(2))))}
          disabled={zoom >= 2}
          title="Phóng to"
          style={{ width: 28, height: 28, border: 0, borderRadius: 5, background: "rgba(255,255,255,0.12)", color: "#fff", cursor: zoom >= 2 ? "not-allowed" : "pointer", fontSize: 18 }}
        >+</button>
      </div>

      <div style={{
        minWidth: "100%", width: "max-content", boxSizing: "border-box",
        display: "flex", flexDirection: "column", alignItems: "center",
        padding: "58px 20px 20px"
      }}>
      {pageImages && pageImages.map((imgUrl, index) => {
        const pageNumber = index + 1;
        const pageZones = zones.filter(z => z.page === pageNumber);
        
        const pageDim = pageDimensions?.find(p => p.page === pageNumber);
        const pdfWidth = pageDim ? pageDim.width : 595.28;
        const scale = pageWidth / pdfWidth;

        return (
          <PageCanvas
            key={`page_${pageNumber}`}
            imgUrl={imgUrl}
            token={token}
            pageWidth={pageWidth}
            scale={scale}
            pageNumber={pageNumber}
            pageZones={pageZones}
            pageTextBlocks={textBlocks.filter(tb => tb.page === pageNumber)}
            mode={mode}
            labeledZones={labeledZones}
            mergeSelection={mergeSelection}
            activeZoneIdx={activeZoneIdx}
            onZoneClick={readOnly ? () => {} : onZoneClick}
            onTextBlockClick={onTextBlockClick}
            onZonesChange={readOnly ? undefined : onZonesChange}
            allZones={zones}
            readOnly={readOnly}
            aiPredictions={aiPredictions}
            fieldDetails={fieldDetails}
          />
        );
      })}
      </div>
    </div>
  );
}

// ─── PageCanvas: renders one page with drag-to-add, click-to-remove, etc. ─────

interface PageCanvasProps {
  imgUrl: string;
  token: string | null;
  pageWidth: number;
  scale: number;
  pageNumber: number;
  pageZones: Zone[];
  pageTextBlocks: TextBlock[];
  mode: PreviewMode;
  labeledZones: Record<string, string>;
  mergeSelection: Set<string>;
  activeZoneIdx?: string | null;
  onZoneClick: (zoneIdx: number) => void;
  onTextBlockClick?: (text: string) => void;
  onZonesChange?: (newZones: Zone[]) => void;
  allZones: Zone[];
  readOnly?: boolean;
  aiPredictions: Record<string, AiPred>;
  fieldDetails: Record<string, { num: number; label: string }>;
}

function PageCanvas({
  imgUrl, token, pageWidth, scale, pageNumber, pageZones, pageTextBlocks,
  mode, labeledZones, mergeSelection, activeZoneIdx, onZoneClick, onTextBlockClick, onZonesChange, allZones, readOnly,
  aiPredictions, fieldDetails
}: PageCanvasProps) {
  const [blobUrl, setBlobUrl] = useState<string>("");
  // Drawing state for "add" mode
  const [drawing, setDrawing] = useState(false);
  const [drawStart, setDrawStart] = useState<{x: number, y: number} | null>(null);
  const [drawRect, setDrawRect] = useState<{x: number, y: number, w: number, h: number} | null>(null);
  const [adjustment, setAdjustment] = useState<{
    zoneIdx: string;
    handle: string;
    startX: number;
    startY: number;
    original: Zone;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch image via blob URL (to pass Bearer token)
  useEffect(() => {
    if (!imgUrl) return;
    const url = resolveApiAssetUrl(imgUrl);
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(res => { if (!res.ok) throw new Error("Status " + res.status); return res.blob(); })
      .then(blob => setBlobUrl(URL.createObjectURL(blob)))
      .catch(err => { console.error("Image fetch error:", err); setBlobUrl("ERROR"); });
    return () => { if (blobUrl && blobUrl !== "ERROR") URL.revokeObjectURL(blobUrl); };
  }, [imgUrl, token]);

  const updateZone = useCallback((zoneIdx: string, updater: (zone: Zone) => Zone) => {
    if (!onZonesChange) return;
    onZonesChange(allZones.map(zone => String(zone.idx) === zoneIdx ? updater(zone) : zone));
  }, [allZones, onZonesChange]);

  // Move/resize the selected region while preserving PDF coordinates.
  useEffect(() => {
    if (!adjustment || mode !== 'adjust') return;

    const handleMove = (event: MouseEvent) => {
      event.preventDefault();
      const dx = (event.clientX - adjustment.startX) / scale;
      const dy = (event.clientY - adjustment.startY) / scale;
      const source = adjustment.original;
      const minimumSize = 3;
      let { x, y, width, height } = source;

      if (adjustment.handle === 'move') {
        x = Math.max(0, source.x + dx);
        y = Math.max(0, source.y + dy);
      } else {
        if (adjustment.handle.includes('e')) width = Math.max(minimumSize, source.width + dx);
        if (adjustment.handle.includes('s')) height = Math.max(minimumSize, source.height + dy);
        if (adjustment.handle.includes('w')) {
          const nextX = Math.min(source.x + source.width - minimumSize, Math.max(0, source.x + dx));
          width = source.width + source.x - nextX;
          x = nextX;
        }
        if (adjustment.handle.includes('n')) {
          const nextY = Math.min(source.y + source.height - minimumSize, Math.max(0, source.y + dy));
          height = source.height + source.y - nextY;
          y = nextY;
        }
      }

      updateZone(adjustment.zoneIdx, zone => ({ ...zone, x, y, width, height }));
    };

    const handleUp = () => setAdjustment(null);
    window.addEventListener('mousemove', handleMove);
    window.addEventListener('mouseup', handleUp, { once: true });
    return () => {
      window.removeEventListener('mousemove', handleMove);
      window.removeEventListener('mouseup', handleUp);
    };
  }, [adjustment, mode, scale, updateZone]);

  // Fine adjustment: arrows move about one screen pixel at 100%; Shift moves 10x.
  useEffect(() => {
    if (mode !== 'adjust' || !activeZoneIdx) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      const directions: Record<string, [number, number]> = {
        ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1],
      };
      const direction = directions[event.key];
      if (!direction) return;
      event.preventDefault();
      const screenPixels = event.shiftKey ? 10 : 1;
      const step = screenPixels / scale;
      updateZone(activeZoneIdx, zone => ({
        ...zone,
        x: Math.max(0, zone.x + direction[0] * step),
        y: Math.max(0, zone.y + direction[1] * step),
      }));
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeZoneIdx, mode, scale, updateZone]);

  // ── Mouse handlers for "add" mode ──────────────────────────────────────────
  const getRelativePos = useCallback((e: React.MouseEvent) => {
    if (!containerRef.current) return { x: 0, y: 0 };
    const rect = containerRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (mode !== 'add') return;
    e.preventDefault();
    const pos = getRelativePos(e);
    setDrawing(true);
    setDrawStart(pos);
    setDrawRect({ x: pos.x, y: pos.y, w: 0, h: 0 });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!drawing || !drawStart || mode !== 'add') return;
    const pos = getRelativePos(e);
    setDrawRect({
      x: Math.min(pos.x, drawStart.x),
      y: Math.min(pos.y, drawStart.y),
      w: Math.abs(pos.x - drawStart.x),
      h: Math.abs(pos.y - drawStart.y),
    });
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!drawing || !drawRect || mode !== 'add') return;
    setDrawing(false);
    setDrawStart(null);
    setDrawRect(null);

    // Minimum 10x10 px to count as a real zone
    if (drawRect.w < 10 || drawRect.h < 10) return;

    // Convert pixel coords back to PDF coordinates (scale = pageWidth / 595.28)
    const pdfX = drawRect.x / scale;
    const pdfY = drawRect.y / scale;
    const pdfW = drawRect.w / scale;
    const pdfH = drawRect.h / scale;

    const newZone: Zone = {
      idx: Date.now(),
      page: pageNumber,
      x: pdfX,
      y: pdfY,
      width: pdfW,
      height: pdfH,
    };
    onZonesChange && onZonesChange([...allZones, newZone]);
  };

  const handleMouseLeave = () => {
    if (drawing) {
      setDrawing(false);
      setDrawStart(null);
      setDrawRect(null);
    }
  };

  // ── Zone click handler ──────────────────────────────────────────────────────
  const handleZoneClick = (e: React.MouseEvent, zone: Zone) => {
    e.preventDefault();
    e.stopPropagation();
    if (mode === 'remove') {
      // Actually remove the zone from the list
      onZonesChange && onZonesChange(allZones.filter(z => z.idx !== zone.idx));
    } else {
      onZoneClick(zone.idx);
    }
  };

  const startAdjustment = (e: React.MouseEvent, zone: Zone, handle: string) => {
    if (mode !== 'adjust') return;
    e.preventDefault();
    e.stopPropagation();
    if (activeZoneIdx !== String(zone.idx)) onZoneClick(zone.idx);
    setAdjustment({
      zoneIdx: String(zone.idx),
      handle,
      startX: e.clientX,
      startY: e.clientY,
      original: { ...zone },
    });
  };

  if (blobUrl === "ERROR") return (
    <div style={{ padding: 40, color: "red", textAlign: "center", background: "#fff", marginBottom: 20, width: pageWidth, borderRadius: 4 }}>
      ❌ Lỗi tải trang {pageNumber}. Vui lòng thử lại.
    </div>
  );
  if (!blobUrl) return (
    <div style={{ padding: 40, color: "#64748b", background: "#fff", marginBottom: 20, width: pageWidth, borderRadius: 4, textAlign: "center" }}>
      ⏳ Đang tải trang {pageNumber}...
    </div>
  );

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative", marginBottom: 20,
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
        width: pageWidth,
        background: "white",
            cursor: readOnly ? 'default' : (mode === 'add' ? 'crosshair' : 'default'),
        userSelect: 'none',
        pointerEvents: readOnly ? 'none' : 'auto',
      }}
      onMouseDown={readOnly ? undefined : handleMouseDown}
      onMouseMove={readOnly ? undefined : handleMouseMove}
      onMouseUp={readOnly ? undefined : handleMouseUp}
      onMouseLeave={readOnly ? undefined : handleMouseLeave}
    >
      <img src={blobUrl} style={{ width: "100%", display: "block", pointerEvents: "none" }} alt={`Page ${pageNumber}`} />

      {/* Zone overlays */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none" }}>
        {pageZones.map((zone, i) => {
          const idxStr = zone.idx.toString();
          const isLabeled = !!labeledZones[idxStr];
          const isMergeSelected = mergeSelection.has(idxStr);
          const pred = aiPredictions[idxStr];
          const conf = pred?.confidence ?? zone.confidence ?? -1;

          // Color logic: priority = labeled > mode-specific > confidence-based
          let borderColor: string;
          let bgColor: string;
          let cursor = "pointer";
          let isActive = activeZoneIdx === idxStr;

          if (isActive) {
            borderColor = "#2563eb";
            bgColor = "rgba(37,99,235,0.4)";
          } else if (mode === 'remove') {
            borderColor = "#ef4444";
            bgColor = "rgba(239,68,68,0.1)";
            cursor = "not-allowed";
          } else if (mode === 'merge') {
            if (isMergeSelected) {
              borderColor = "#3b82f6";
              bgColor = "rgba(59,130,246,0.3)";
            } else {
              borderColor = "#94a3b8";
              bgColor = "transparent";
            }
          } else if (isLabeled) {
            // Admin đã confirm → xanh lá
            borderColor = "#22c55e";
            bgColor = "rgba(34,197,94,0.18)";
          } else if (conf >= 0.85) {
            // AI chắc cao → tím (AI predicted, chờ confirm)
            borderColor = "#7c3aed";
            bgColor = "rgba(124,58,237,0.12)";
          } else if (conf >= 0.5) {
            // AI khá chắc → vàng
            borderColor = "#eab308";
            bgColor = "rgba(234,179,8,0.15)";
          } else if (conf >= 0) {
            // AI không chắc → cam
            borderColor = "#f97316";
            bgColor = "rgba(249,115,22,0.12)";
          } else {
            // Chưa predict → vàng mặc định
            borderColor = "#eab308";
            bgColor = "rgba(234,179,8,0.2)";
          }

          if (mode === 'add') cursor = "crosshair";
          if (mode === 'adjust') cursor = isActive ? "move" : "pointer";

          // Label text hiển thị trên zone
          let displayLabel = "";
          let hoverTitle = "";
          
          // Ưu tiên dùng detail.num (rank toàn form) thay vì index local của trang
          const fieldId = isLabeled ? labeledZones[idxStr] : null;
          const detail = fieldId ? fieldDetails[fieldId] : null;
          // Số thứ tự nhất quán: dùng detail.num nếu đã labeled, fallback về index trong allZones
          const globalSeqNum = detail?.num ?? (allZones.findIndex(z => String(z.idx) === idxStr) + 1);
          
          if (mode === 'remove') {
            hoverTitle = `Xóa vùng #${globalSeqNum}`;
          } else if (mode === 'merge') {
            hoverTitle = `${isMergeSelected ? "Bỏ chọn" : "Chọn"} vùng #${globalSeqNum}`;
          } else if (isLabeled) {
            if (detail) {
              displayLabel = `[${detail.num}] ${detail.label}`;
              hoverTitle = `✅ Đã dán: [${detail.num}] ${detail.label}`;
            } else {
              displayLabel = fieldId!;
              hoverTitle = `✅ Đã dán: ${fieldId}`;
            }
          } else if (pred) {
            displayLabel = pred.label;
            hoverTitle = `🤖 AI đề xuất: ${pred.label} (${Math.round(conf*100)}%)`;
          } else {
            displayLabel = zone.suggested_label || `+`;
            hoverTitle = zone.suggested_label
              ? `Chưa dán nhãn: ${zone.suggested_label}`
              : `Vùng mới - nhấp để dán nhãn`;
          }

          return (
            <div
              key={`zone_${zone.idx}_${i}`}
              onClick={(e) => handleZoneClick(e, zone)}
              onMouseDown={(e) => mode === 'adjust'
                ? startAdjustment(e, zone, 'move')
                : (() => { e.preventDefault(); e.stopPropagation(); })()}
              style={{
                position: "absolute",
                left: zone.x * scale,
                top: zone.y * scale,
                width: zone.width * scale,
                height: zone.height * scale,
                border: `2px solid ${borderColor}`,
                backgroundColor: bgColor,
                cursor,
                pointerEvents: mode === 'add' ? "none" : "auto",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.15s",
                boxSizing: "border-box",
                boxShadow: isActive ? "0 0 0 4px rgba(37,99,235,0.3)" : "none",
                zIndex: isActive ? 10 : 2,
              }}
              title={hoverTitle}
            >
              {mode === 'remove' && (
                <span style={{ fontSize: 14, color: "#ef4444", fontWeight: "bold", background: "rgba(255,255,255,0.85)", padding: "0 4px", borderRadius: 2, lineHeight: 1.4 }}>✕</span>
              )}
              {mode !== 'remove' && (
                <span style={{
                  fontSize: 10, fontWeight: "bold", color: borderColor,
                  background: "rgba(255,255,255,0.88)", padding: "0 3px", borderRadius: 2, lineHeight: 1.4,
                  maxWidth: "95%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>
                  {displayLabel}
                </span>
              )}
              {mode === 'adjust' && isActive && ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'].map(handle => {
                const positions: Record<string, React.CSSProperties> = {
                  nw: { left: -5, top: -5 }, n: { left: '50%', top: -5, transform: 'translateX(-50%)' },
                  ne: { right: -5, top: -5 }, e: { right: -5, top: '50%', transform: 'translateY(-50%)' },
                  se: { right: -5, bottom: -5 }, s: { left: '50%', bottom: -5, transform: 'translateX(-50%)' },
                  sw: { left: -5, bottom: -5 }, w: { left: -5, top: '50%', transform: 'translateY(-50%)' },
                };
                const cursors: Record<string, string> = {
                  nw: 'nwse-resize', n: 'ns-resize', ne: 'nesw-resize', e: 'ew-resize',
                  se: 'nwse-resize', s: 'ns-resize', sw: 'nesw-resize', w: 'ew-resize',
                };
                return <span
                  key={handle}
                  onMouseDown={(event) => startAdjustment(event, zone, handle)}
                  style={{
                    position: 'absolute', width: 10, height: 10, borderRadius: 2,
                    background: '#fff', border: '2px solid #2563eb', boxSizing: 'border-box',
                    pointerEvents: 'auto', cursor: cursors[handle], zIndex: 20,
                    ...positions[handle],
                  }}
                />;
              })}
            </div>
          );
        })}

        {/* Text Blocks Overlay (Click-to-Label) */}
        {mode === 'label' && pageTextBlocks && pageTextBlocks.map((tb, i) => (
          <div
            key={`tb_${i}`}
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              if (onTextBlockClick) onTextBlockClick(tb.text);
            }}
            onMouseDown={(e) => { e.preventDefault(); e.stopPropagation(); }}
            style={{
              position: "absolute",
              left: tb.x * scale,
              top: tb.y * scale,
              width: tb.width * scale,
              height: tb.height * scale,
              cursor: activeZoneIdx ? "pointer" : "default",
              backgroundColor: activeZoneIdx ? "rgba(59, 130, 246, 0.1)" : "transparent",
              border: activeZoneIdx ? "1px solid rgba(59, 130, 246, 0.2)" : "none",
              color: "transparent", // Hide text, just show hover box
              boxSizing: "border-box",
              transition: "background-color 0.15s",
              zIndex: 1,
              pointerEvents: activeZoneIdx ? "auto" : "none",
            }}
            title={activeZoneIdx ? `Nhấn để dùng chữ: "${tb.text}"` : ""}
            onMouseEnter={(e) => {
              if (activeZoneIdx) {
                e.currentTarget.style.backgroundColor = "rgba(59, 130, 246, 0.3)";
                e.currentTarget.style.borderColor = "rgba(59, 130, 246, 0.5)";
              }
            }}
            onMouseLeave={(e) => {
              if (activeZoneIdx) {
                e.currentTarget.style.backgroundColor = "rgba(59, 130, 246, 0.1)";
                e.currentTarget.style.borderColor = "rgba(59, 130, 246, 0.2)";
              }
            }}
          />
        ))}
      </div>

      {/* Drawing rectangle preview (while dragging in add mode) */}
      {drawRect && drawRect.w > 2 && drawRect.h > 2 && (
        <div style={{
          position: "absolute",
          left: drawRect.x,
          top: drawRect.y,
          width: drawRect.w,
          height: drawRect.h,
          border: "2px dashed #3b82f6",
          backgroundColor: "rgba(59,130,246,0.15)",
          pointerEvents: "none",
          boxSizing: "border-box",
        }} />
      )}

      {/* Add mode hint overlay at top */}
      {mode === 'add' && (
        <div style={{
          position: "absolute", top: 6, left: "50%", transform: "translateX(-50%)",
          background: "rgba(59,130,246,0.9)", color: "#fff", fontSize: 11, fontWeight: 600,
          padding: "3px 10px", borderRadius: 99, pointerEvents: "none", whiteSpace: "nowrap"
        }}>
          Kéo để vẽ vùng mới
        </div>
      )}
      {mode === 'adjust' && (
        <div style={{
          position: "absolute", top: 6, left: "50%", transform: "translateX(-50%)",
          background: "rgba(37,99,235,0.92)", color: "#fff", fontSize: 11, fontWeight: 600,
          padding: "4px 12px", borderRadius: 99, pointerEvents: "none", whiteSpace: "nowrap", zIndex: 30,
        }}>
          Chọn rồi kéo khung/điểm neo · Phím mũi tên để căn chính xác
        </div>
      )}
    </div>
  );
}
