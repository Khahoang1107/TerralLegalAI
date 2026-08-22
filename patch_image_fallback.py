import os

filepath = r"d:\TerraLegalAI\frontend\components\PdfFormPreview.tsx"

new_content = """"use client";

import React, { useState, useEffect, useRef } from "react";

interface Zone {
  idx: number;
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface PdfFormPreviewProps {
  pageImages: string[];
  zones: Zone[];
  mode: 'label' | 'add' | 'remove' | 'merge';
  labeledZones: Record<string, string>;
  mergeSelection: Set<string>;
  onZoneClick: (zoneIdx: number) => void;
}

export default function PdfFormPreview({
  pageImages,
  zones,
  mode,
  labeledZones,
  mergeSelection,
  onZoneClick
}: PdfFormPreviewProps) {
  const [pageWidth, setPageWidth] = useState<number>(800);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        const cw = containerRef.current.clientWidth;
        if (cw > 100) {
          setPageWidth(cw - 40);
        }
      }
    };
    updateWidth();
    window.addEventListener("resize", updateWidth);
    return () => window.removeEventListener("resize", updateWidth);
  }, []);

  // Tỷ lệ scale: PyMuPDF toạ độ dựa trên A4 chuẩn (595.28 pt).
  const scale = pageWidth / 595.28;
  const token = typeof window !== 'undefined' 
    ? (localStorage.getItem("terralegal_access_token") ?? sessionStorage.getItem("terralegal_access_token"))
    : null;

  return (
    <div 
      ref={containerRef}
      style={{ 
        width: "100%", 
        height: "100%", 
        overflowY: "auto", 
        background: "#e2e8f0", 
        display: "flex", 
        flexDirection: "column", 
        alignItems: "center",
        padding: "20px 0",
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0
      }}
    >
      {pageImages && pageImages.map((imgUrl, index) => {
        const pageNumber = index + 1;
        const pageZones = zones.filter(z => z.page === pageNumber);
        
        // Fetch image with Auth token (requires a trick, or we just render an img and pass token in src? No, img src doesn't send Bearer. We have to fetch and create blob url)
        return <PageImage key={`page_${pageNumber}`} imgUrl={imgUrl} token={token} pageWidth={pageWidth} scale={scale} pageNumber={pageNumber} pageZones={pageZones} mode={mode} labeledZones={labeledZones} mergeSelection={mergeSelection} onZoneClick={onZoneClick} />;
      })}
    </div>
  );
}

function PageImage({ imgUrl, token, pageWidth, scale, pageNumber, pageZones, mode, labeledZones, mergeSelection, onZoneClick }: any) {
  const [blobUrl, setBlobUrl] = useState<string>("");

  useEffect(() => {
    fetch(`http://localhost:8000${imgUrl}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {}
    })
    .then(res => res.blob())
    .then(blob => {
      const url = URL.createObjectURL(blob);
      setBlobUrl(url);
    })
    .catch(err => console.error("Error fetching image:", err));
    
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    }
  }, [imgUrl, token]);

  if (!blobUrl) return <div style={{ padding: 40, color: "#64748b" }}>Đang tải trang {pageNumber}...</div>;

  return (
    <div style={{ position: "relative", marginBottom: 20, boxShadow: "0 4px 12px rgba(0,0,0,0.15)", width: pageWidth, minHeight: pageWidth * 1.414, background: "white" }}>
      <img src={blobUrl} style={{ width: "100%", display: "block" }} alt={`Page ${pageNumber}`} />
      
      {/* Overlay */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none" }}>
        {pageZones.map((zone: any) => {
          const isLabeled = !!labeledZones[zone.idx];
          const isMergeSelected = mergeSelection.has(zone.idx.toString());
          
          let borderColor = isLabeled ? "#22c55e" : "#eab308";
          let bgColor = isLabeled ? "rgba(34,197,94,0.1)" : "rgba(234,179,8,0.2)";
          
          if (mode === "remove") {
            borderColor = "#ef4444";
            bgColor = "rgba(239,68,68,0.1)";
          } else if (mode === "merge") {
            if (isMergeSelected) {
              borderColor = "#3b82f6";
              bgColor = "rgba(59,130,246,0.3)";
            } else {
              borderColor = "#94a3b8";
              bgColor = "transparent";
            }
          }

          return (
            <div 
              key={`zone_${zone.idx}`}
              onClick={() => onZoneClick(zone.idx)}
              style={{
                position: "absolute",
                left: zone.x * scale,
                top: zone.y * scale,
                width: zone.width * scale,
                height: zone.height * scale,
                border: `2px solid ${borderColor}`,
                backgroundColor: bgColor,
                cursor: "pointer",
                pointerEvents: "auto",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.2s"
              }}
              title={labeledZones[zone.idx] ? `Trường: ${labeledZones[zone.idx]}` : "Chưa dán nhãn"}
            >
              <span style={{ 
                fontSize: 10, 
                fontWeight: "bold", 
                color: borderColor,
                background: "rgba(255,255,255,0.8)",
                padding: "0 2px",
                borderRadius: 2
              }}>
                {labeledZones[zone.idx] ? labeledZones[zone.idx] : `[${zone.idx}]`}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
"""

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)

# Update page.tsx to pass pageImages
filepath_page = r"d:\TerraLegalAI\frontend\app\page.tsx"
with open(filepath_page, "r", encoding="utf-8") as f:
    content_page = f.read()

content_page = content_page.replace(
    "previewUrl={previewData.preview_url}",
    "pageImages={previewData.page_images || [previewData.preview_url]}"
)
with open(filepath_page, "w", encoding="utf-8") as f:
    f.write(content_page)
