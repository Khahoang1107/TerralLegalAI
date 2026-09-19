with open('frontend/app/page.tsx', 'r', encoding='utf-8') as f:
    text = f.read()

target = """    for (const section of formSections) {
      const secName = section.name.trim() || "Chưa đặt tên";
      if (!section.name.trim()) {
        showToast("Vui lòng nhập tên cho tất cả các nhóm logic.", "error");
        return;
      }
      const memberCount = section.mode === "one_of" """

replacement = """    const invalidSection = formSections.find(section => {
      const memberCount = section.mode === "one_of" """

# Also handle CRLF
if target.replace('\n', '\r\n') in text:
    text = text.replace(target.replace('\n', '\r\n'), replacement.replace('\n', '\r\n'), 1)
    print("Replaced with CRLF")
elif target in text:
    text = text.replace(target, replacement, 1)
    print("Replaced with LF")
else:
    print("Target not found!")

with open('frontend/app/page.tsx', 'w', encoding='utf-8') as f:
    f.write(text)
