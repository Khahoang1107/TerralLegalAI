import re

file_path = "d:/TerraLegalAI/frontend/app/page.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Part 1: handleAnalyzeDocx
target_1 = """      const initialLabeledZones: Record<string, string> = {};
      const initialFieldOrder: string[] = [];
      let fieldCounter = 1;

      // Auto-assign labels for zones with suggestions
      zones.forEach((zone: any) => {
        const suggestion = zone.suggested_label || zone.ai_label;
        if (suggestion) {
          const fieldId = `field_${9000 + fieldCounter++}`;
          initialLabeledZones[String(zone.idx)] = fieldId;
          initialFieldOrder.push(fieldId);
        }
      });

      labeledZonesRef.current = initialLabeledZones;
      fieldOrderRef.current = initialFieldOrder;
      setFieldData({});"""

replacement_1 = """      const initialLabeledZones: Record<string, string> = {};
      const initialFieldOrder: string[] = [];
      const initialFieldData: Record<string, string> = {};
      let fieldCounter = 1;

      // Auto-assign labels for zones with suggestions
      zones.forEach((zone: any) => {
        const suggestion = zone.suggested_label || zone.ai_label || zone.fallback_name;
        if (suggestion) {
          const fieldId = `field_${9000 + fieldCounter++}`;
          initialLabeledZones[String(zone.idx)] = fieldId;
          initialFieldOrder.push(fieldId);
          initialFieldData[fieldId] = suggestion;
        }
      });

      labeledZonesRef.current = initialLabeledZones;
      fieldOrderRef.current = initialFieldOrder;
      setFieldData(initialFieldData);"""

content = content.replace(target_1, replacement_1)

# Part 2: handleAIPredict
target_2 = """  const handleAIPredict = async () => {
    if (!previewData?.temp_id) return;
    setIsPredictingAI(true);
    try {
      const res = await formsApi.aiPredict(previewData.temp_id, editableZones);
      setEditableZones(res.zones);
      
      const newLabeledSnapshot = { ...labeledSnapshot };
      const newFieldOrder = [...fieldOrderSnapshot];
      let addedCount = 0;
      let fieldCounter = manualCounterRef.current;
      
      res.zones.forEach((z: any) => {
        if (z.suggested_label) {
          const idxStr = String(z.idx);
          if (!newLabeledSnapshot[idxStr] && !labeledZonesRef.current[idxStr]) {
            const fieldId = `field_${fieldCounter++}`;
            newLabeledSnapshot[idxStr] = fieldId;
            labeledZonesRef.current[idxStr] = fieldId;
            newFieldOrder.push(fieldId);
            fieldOrderRef.current.push(fieldId);
            addedCount++;
          }
        }
      });
      manualCounterRef.current = fieldCounter;
      setLabeledSnapshot(newLabeledSnapshot);
      setFieldOrderSnapshot(newFieldOrder);
      setLabeledCount(Object.keys(newLabeledSnapshot).length);"""

replacement_2 = """  const handleAIPredict = async () => {
    if (!previewData?.temp_id) return;
    setIsPredictingAI(true);
    try {
      const userLabels: Record<string, string> = {};
      Object.entries(labeledSnapshot).forEach(([idxStr, fieldId]) => {
        if (fieldData[fieldId] && fieldData[fieldId].trim() !== "") {
          userLabels[idxStr] = fieldData[fieldId];
        }
      });

      const res = await formsApi.aiPredict(previewData.temp_id, editableZones, userLabels);
      setEditableZones(res.zones);
      
      const newLabeledSnapshot = { ...labeledSnapshot };
      const newFieldOrder = [...fieldOrderSnapshot];
      const newFieldData = { ...fieldData };
      let addedCount = 0;
      let fieldCounter = manualCounterRef.current;
      
      res.zones.forEach((z: any) => {
        if (z.suggested_label) {
          const idxStr = String(z.idx);
          if (!newLabeledSnapshot[idxStr] && !labeledZonesRef.current[idxStr]) {
            const fieldId = `field_${fieldCounter++}`;
            newLabeledSnapshot[idxStr] = fieldId;
            labeledZonesRef.current[idxStr] = fieldId;
            newFieldOrder.push(fieldId);
            fieldOrderRef.current.push(fieldId);
            newFieldData[fieldId] = z.suggested_label;
            addedCount++;
          } else if (newLabeledSnapshot[idxStr] && !newFieldData[newLabeledSnapshot[idxStr]]) {
            newFieldData[newLabeledSnapshot[idxStr]] = z.suggested_label;
          }
        }
      });
      manualCounterRef.current = fieldCounter;
      setLabeledSnapshot(newLabeledSnapshot);
      setFieldOrderSnapshot(newFieldOrder);
      setLabeledCount(Object.keys(newLabeledSnapshot).length);
      setFieldData(newFieldData);"""

content = content.replace(target_2, replacement_2)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patched page.tsx successfully!")
