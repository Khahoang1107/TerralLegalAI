import os

filepath = r"d:\TerraLegalAI\frontend\app\page.tsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

start_idx = content.find("function FormsView() {")
if start_idx == -1:
    print("Cannot find FormsView")
    exit(1)

# Find matching brace
brace_count = 0
end_idx = -1
in_function = False
for i in range(start_idx, len(content)):
    if content[i] == '{':
        brace_count += 1
        in_function = True
    elif content[i] == '}':
        brace_count -= 1
        if in_function and brace_count == 0:
            end_idx = i + 1
            break

if end_idx == -1:
    print("Cannot find end of FormsView")
    exit(1)

forms_view_content = content[start_idx:end_idx]

# Imports needed for FormsAdmin.tsx
imports = """"use client";
import React, { useEffect, useState, useRef, useCallback } from "react";
import { formsApi } from "@/lib/api";
import { AlertCircle, Plus, CheckCircle2, X } from "lucide-react";
// We need to import Toast or pass it. It's better to just redefine the Toast usage or pass showToast down.
// Actually, FormsView uses `useToast` which is defined in page.tsx!
"""

print(forms_view_content[:100])
