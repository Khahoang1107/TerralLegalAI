import ReactMarkdown from "react-markdown";
import { Bot, User } from "lucide-react";
import type { Citation } from "@/lib/api";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-4 p-4 md:p-6 ${isUser ? "bg-white dark:bg-[#0a0a0a]" : "bg-gray-50 dark:bg-[#111111]"}`}>
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-white ${isUser ? "bg-blue-600" : "bg-emerald-600"}`}>
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div className="min-w-0 flex-1 text-sm leading-7 text-gray-800 dark:text-gray-200 md:text-base">
        <ReactMarkdown>{message.content}</ReactMarkdown>

        {message.citations && message.citations.length > 0 && (
          <div className="mt-4 border-t border-gray-200 pt-3 dark:border-gray-700">
            <p className="mb-2 text-xs font-semibold uppercase text-gray-500">Nguồn tham khảo</p>
            <div className="space-y-2">
              {message.citations.map((citation, index) => (
                <div key={`${citation.source_name}-${index}`} className="text-xs text-gray-600 dark:text-gray-400">
                  <span className="font-medium">{citation.source_name}</span>
                  {citation.article ? ` - ${citation.article}` : ""}
                  {citation.clause ? `, ${citation.clause}` : ""}
                  {citation.text_snippet ? <p className="mt-1">{citation.text_snippet}</p> : null}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
