"use client";

import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, RefreshCw } from 'lucide-react';
import MessageBubble, { Message } from './MessageBubble';
import { chatApi } from '@/lib/api';

export default function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([{
    id: 'welcome-message',
    role: 'assistant',
    content: 'Chào bạn! Tôi là trợ lý ảo tư vấn thủ tục hành chính đất đai tỉnh Vĩnh Long. Tôi có thể giúp gì cho bạn hôm nay?'
  }]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [procedureFilter, setProcedureFilter] = useState('all');
  
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim()
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Gọi RAG API
      const response = await chatApi.sendMessage({
        question: userMessage.content,
        procedure_filter: procedureFilter === 'all' ? undefined : procedureFilter
      });

      const assistantMessage: Message = {
        id: response.message_id || (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        citations: response.citations
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error: unknown) {
      console.error('Error calling chat API:', error);
      
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Xin lỗi, đã xảy ra lỗi kết nối với máy chủ. Vui lòng thử lại sau.'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setMessages([{
      id: 'welcome-message',
      role: 'assistant',
      content: 'Chào bạn! Tôi là trợ lý ảo tư vấn thủ tục hành chính đất đai tỉnh Vĩnh Long. Tôi có thể giúp gì cho bạn hôm nay?'
    }]);
  };

  return (
    <div className="flex flex-col h-full bg-white dark:bg-[#0a0a0a] border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-[#111111]">
        <div>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200">TerraLegalAI</h2>
          <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Trợ lý ảo pháp luật đất đai</p>
        </div>
        
        <div className="flex items-center gap-4">
          <select 
            value={procedureFilter}
            onChange={(e) => setProcedureFilter(e.target.value)}
            className="text-sm bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-md py-1.5 px-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">Tất cả thủ tục</option>
            <option value="chuyen_nhuong">Chuyển nhượng</option>
            <option value="cap_doi">Cấp đổi GCN</option>
          </select>
          
          <button 
            onClick={handleReset}
            className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
            title="Bắt đầu hội thoại mới"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto scroll-smooth">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && (
          <div className="flex gap-4 p-4 md:p-6 bg-gray-50 dark:bg-[#111111]">
            <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-white flex-shrink-0">
              <Loader2 className="w-5 h-5 animate-spin" />
            </div>
            <div className="flex items-center">
              <p className="text-sm text-gray-500 dark:text-gray-400 animate-pulse">
                Đang tìm kiếm thông tin luật...
              </p>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white dark:bg-[#0a0a0a] border-t border-gray-200 dark:border-gray-800">
        <form 
          onSubmit={handleSubmit}
          className="relative flex items-end max-w-4xl mx-auto bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-2xl overflow-hidden focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent transition-all shadow-sm"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e);
              }
            }}
            placeholder="Ví dụ: Sang tên sổ đỏ cần những giấy tờ gì?"
            className="w-full max-h-32 min-h-[56px] py-4 pl-4 pr-12 bg-transparent text-gray-800 dark:text-gray-200 resize-none outline-none text-sm md:text-base placeholder-gray-400"
            rows={1}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 bottom-2 p-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:bg-gray-300 disabled:dark:bg-gray-700 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </form>
        <p className="text-center text-xs text-gray-400 dark:text-gray-500 mt-3">
          TerraLegalAI có thể cung cấp thông tin không chính xác. Hãy luôn kiểm tra lại với cơ quan nhà nước.
        </p>
      </div>
    </div>
  );
}
