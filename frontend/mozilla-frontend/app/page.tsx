"use client";

import React, { useState, useEffect, useRef } from "react";

interface Source {
  source: string;
  text: string;
  score: number;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  tokens?: number;
  model?: string;
  conflict?: string;
}

interface HealthStatus {
  status: string;
  services: {
    embeddings_server: string;
    llm_server: string;
  };
}

function MarkdownContent({ content, theme }: { content: string; theme: "dark" | "light" }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  
  let inList = false;
  let listItems: React.ReactNode[] = [];
  
  const parseInline = (text: string) => {
    const regex = /(\*\*.*?\*\*|`.*?`)/g;
    const splitParts = text.split(regex);
    
    return splitParts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={index} className={`font-extrabold ${
            theme === "dark" ? "text-[#c084fc]" : "text-purple-700"
          }`}>
            {part.slice(2, -2)}
          </strong>
        );
      } else if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={index} className={`px-1.5 py-0.5 rounded font-mono text-xs border ${
            theme === "dark" 
              ? "bg-purple-950/40 border-purple-500/20 text-purple-300" 
              : "bg-purple-50 border-purple-200 text-purple-800"
          }`}>
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
  };

  const listClass = `list-disc pl-6 space-y-1.5 my-2 transition-colors duration-300 ${
    theme === "dark" ? "text-zinc-300" : "text-zinc-700"
  }`;

  lines.forEach((line, idx) => {
    const trimmed = line.trim();
    
    if (trimmed.startsWith("###")) {
      if (inList) {
        elements.push(<ul key={`list-${idx}`} className={listClass}>{listItems}</ul>);
        listItems = [];
        inList = false;
      }
      elements.push(
        <h3 key={idx} className={`text-sm font-bold mt-4 mb-2 tracking-wide transition-colors duration-300 ${
          theme === "dark" ? "text-purple-300" : "text-purple-800"
        }`}>
          {parseInline(trimmed.replace(/^###\s*/, ""))}
        </h3>
      );
      return;
    }
    if (trimmed.startsWith("##")) {
      if (inList) {
        elements.push(<ul key={`list-${idx}`} className={listClass}>{listItems}</ul>);
        listItems = [];
        inList = false;
      }
      elements.push(
        <h2 key={idx} className={`text-base font-extrabold mt-5 mb-2.5 tracking-wide border-b pb-1 transition-colors duration-300 ${
          theme === "dark" ? "text-white border-purple-500/10" : "text-zinc-800 border-purple-200"
        }`}>
          {parseInline(trimmed.replace(/^##\s*/, ""))}
        </h2>
      );
      return;
    }
    if (trimmed.startsWith("#")) {
      if (inList) {
        elements.push(<ul key={`list-${idx}`} className={listClass}>{listItems}</ul>);
        listItems = [];
        inList = false;
      }
      elements.push(
        <h1 key={idx} className={`text-lg font-extrabold mt-6 mb-3 tracking-wide transition-colors duration-300 ${
          theme === "dark" ? "text-white" : "text-zinc-800"
        }`}>
          {parseInline(trimmed.replace(/^#\s*/, ""))}
        </h1>
      );
      return;
    }
    
    if (trimmed.startsWith("*") || trimmed.startsWith("-")) {
      inList = true;
      const cleanLine = trimmed.replace(/^[*+-]\s*/, "");
      listItems.push(
        <li key={idx} className="leading-relaxed">
          {parseInline(cleanLine)}
        </li>
      );
      return;
    }
    
    if (trimmed === "") {
      if (inList) {
        elements.push(<ul key={`list-${idx}`} className={listClass}>{listItems}</ul>);
        listItems = [];
        inList = false;
      }
      return;
    }
    
    if (inList) {
      elements.push(<ul key={`list-${idx}`} className={listClass}>{listItems}</ul>);
      listItems = [];
      inList = false;
    }
    
    elements.push(
      <p key={idx} className={`my-2.5 leading-relaxed transition-colors duration-300 ${
        theme === "dark" ? "text-zinc-200" : "text-zinc-800"
      }`}>
        {parseInline(line)}
      </p>
    );
  });
  
  if (inList) {
    elements.push(<ul key="list-last" className={listClass}>{listItems}</ul>);
  }
  
  return <div className="space-y-1">{elements}</div>;
}

export default function Home() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [chunkCount, setChunkCount] = useState<number>(0);
  const [messages, setMessages] = useState<Message[]>([]);
  const [query, setQuery] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [uploadFeedback, setUploadFeedback] = useState<{ success: boolean; message: string } | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [expandedSources, setExpandedSources] = useState<{ [key: number]: boolean }>({});

  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const API_BASE = "http://127.0.0.1:8000";

  // 1. Fetch Health Status & Database Stats on Mount and Poll
  const fetchStatsAndHealth = async () => {
    try {
      const healthRes = await fetch(`${API_BASE}/api/health`);
      if (healthRes.ok) {
        const healthData = await healthRes.json();
        setHealth(healthData);
      } else {
        setHealth(null);
      }
    } catch (e) {
      setHealth(null);
    }

    try {
      const statsRes = await fetch(`${API_BASE}/api/stats`);
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setChunkCount(statsData.chunk_count);
      }
    } catch (e) {
      // Keep previous chunk count
    }
  };

  useEffect(() => {
    fetchStatsAndHealth();
    const interval = setInterval(fetchStatsAndHealth, 6000);
    return () => clearInterval(interval);
  }, []);

  // 2. Scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isGenerating]);

  // 3. File Selection & Upload
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const filesArray = Array.from(e.target.files);
      setSelectedFiles((prev) => [...prev, ...filesArray]);
      setUploadFeedback(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      const filesArray = Array.from(e.dataTransfer.files);
      setSelectedFiles((prev) => [...prev, ...filesArray]);
      setUploadFeedback(null);
    }
  };

  const removeSelectedFile = (index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const uploadFiles = async () => {
    if (selectedFiles.length === 0) return;

    setIsUploading(true);
    setUploadFeedback(null);

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append("files", file);
    });

    try {
      const res = await fetch(`${API_BASE}/api/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setUploadFeedback({ success: true, message: data.message });
        setSelectedFiles([]);
        fetchStatsAndHealth(); // Update count
      } else {
        setUploadFeedback({ success: false, message: data.detail || "Upload failed." });
      }
    } catch (e) {
      setUploadFeedback({ success: false, message: "Could not reach backend API." });
    } finally {
      setIsUploading(false);
    }
  };

  // 4. Reset Vector Store
  const resetDatabase = async () => {
    if (!confirm("Are you sure you want to clear the vector database? All indexed documents will be lost.")) return;

    try {
      const res = await fetch(`${API_BASE}/api/reset`, { method: "POST" });
      if (res.ok) {
        setChunkCount(0);
        setMessages([]);
        setUploadFeedback({ success: true, message: "Vector store wiped." });
      } else {
        alert("Failed to reset database.");
      }
    } catch (e) {
      alert("Could not reach backend API.");
    }
  };

  // 5. Send Question
  const sendQuestion = async (textToSend?: string) => {
    const messageText = textToSend || query;
    if (!messageText.trim() || isGenerating) return;

    // Add user message
    const newMsg: Message = { role: "user", content: messageText };
    setMessages((prev) => [...prev, newMsg]);
    if (!textToSend) setQuery("");
    setIsGenerating(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: messageText }),
      });

      const data = await res.json();
      if (res.ok) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.answer,
            sources: data.sources,
            tokens: data.tokens,
            model: data.model,
            conflict: data.conflict,
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Error: ${data.detail || "Failed to fetch response."}`,
          },
        ]);
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Error: Could not reach backend API.",
        },
      ]);
    } finally {
      setIsGenerating(false);
    }
  };

  const toggleSources = (index: number) => {
    setExpandedSources((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  // Health checks display variables
  const isHealthy = health?.status === "healthy";
  const embeddingsConnected = health?.services.embeddings_server === "connected";
  const llmConnected = health?.services.llm_server === "connected";

  return (
    <div className={`flex h-screen w-full overflow-hidden transition-colors duration-300 ${
      theme === "dark" ? "bg-[#0c0a12] text-[#f3f4f6]" : "bg-[#f8f6fc] text-zinc-800"
    }`}>
      {/* ---------------------------------------------------------------------
          Sidebar Panel
          --------------------------------------------------------------------- */}
      <aside className={`w-80 flex flex-col p-5 shrink-0 overflow-y-auto transition-colors duration-300 border-r ${
        theme === "dark" ? "bg-[#0d0a15] border-purple-500/10" : "bg-[#f0edf7] border-purple-500/20"
      }`}>
        {/* Logo and Header */}
        <div className="flex items-center gap-3 mb-6">
          <svg className="w-8 h-8 text-purple-500" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z" />
          </svg>
          <div>
            <h1 className={`text-lg font-bold tracking-wide transition-colors ${theme === "dark" ? "text-white" : "text-[#1e1b4b]"}`}>IntelliBuild</h1>
            <p className={`text-xs font-medium transition-colors ${theme === "dark" ? "text-purple-400" : "text-purple-700"}`}>Local RAG Workspace</p>
          </div>
        </div>

        {/* Health Check Indicators */}
        <div className={`border rounded-xl p-4 mb-5 space-y-3 transition-colors duration-300 ${
          theme === "dark" ? "bg-purple-950/20 border-purple-500/10" : "bg-purple-100/40 border-purple-500/20"
        }`}>
          <div className="flex items-center justify-between">
            <span className={`text-xs font-semibold ${theme === "dark" ? "text-purple-300" : "text-purple-800"}`}>System Connection</span>
            <span className={`inline-block w-2.5 h-2.5 rounded-full ${isHealthy ? "bg-emerald-500 shadow-[0_0_8px_#10b981]" : "bg-rose-500 shadow-[0_0_8px_#f43f5e]"}`} />
          </div>
          <div className={`space-y-2 border-t pt-2 text-xs ${theme === "dark" ? "border-purple-500/10" : "border-purple-500/20"}`}>
            <div className="flex justify-between items-center">
              <span className={theme === "dark" ? "text-zinc-400" : "text-zinc-600"}>Embeddings Server (8085)</span>
              <span className={embeddingsConnected ? "text-emerald-400 font-medium" : "text-rose-400 font-medium"}>
                {embeddingsConnected ? "Online" : "Offline"}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className={theme === "dark" ? "text-zinc-400" : "text-zinc-600"}>LLM Server (8086)</span>
              <span className={llmConnected ? "text-emerald-400 font-medium" : "text-rose-400 font-medium"}>
                {llmConnected ? "Online" : "Offline"}
              </span>
            </div>
          </div>
        </div>

        {/* File Drop & Ingestion */}
        <div className="flex-1 flex flex-col">
          <h2 className={`text-xs font-bold uppercase tracking-wider mb-2 transition-colors ${theme === "dark" ? "text-purple-300" : "text-purple-800"}`}>
            Ingest Documents
          </h2>
          
          <div
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all mb-3 group ${
              theme === "dark" 
                ? "border-purple-500/20 hover:border-purple-500/40 bg-purple-950/5 hover:bg-purple-950/10" 
                : "border-purple-500/30 hover:border-purple-500/50 bg-purple-100/20 hover:bg-purple-100/30"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              multiple
              accept=".pdf,.txt,.md"
              className="hidden"
            />
            <svg className="w-8 h-8 text-purple-400/80 mx-auto mb-2 group-hover:scale-105 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
            <span className={`block text-xs font-semibold ${theme === "dark" ? "text-zinc-300" : "text-zinc-700"}`}>Drag & drop files here</span>
            <span className="block text-[10px] text-zinc-500 mt-1">Accepts PDF, MD, TXT</span>
          </div>

          {/* Selected Files List */}
          {selectedFiles.length > 0 && (
            <div className={`border rounded-lg p-2 max-h-40 overflow-y-auto mb-3 space-y-1.5 transition-colors ${
              theme === "dark" ? "bg-[#141021] border-purple-500/10" : "bg-white border-purple-200"
            }`}>
              {selectedFiles.map((file, idx) => (
                <div key={idx} className={`flex justify-between items-center text-xs p-1.5 rounded border transition-colors ${
                  theme === "dark" ? "bg-[#1a162b] border-purple-500/5" : "bg-purple-50/50 border-purple-200"
                }`}>
                  <span className={`truncate max-w-[160px] font-medium ${theme === "dark" ? "text-zinc-300" : "text-zinc-700"}`}>{file.name}</span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeSelectedFile(idx);
                    }}
                    className="text-rose-400 hover:text-rose-300 p-0.5 rounded cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Index Button */}
          {selectedFiles.length > 0 && (
            <button
              onClick={uploadFiles}
              disabled={isUploading}
              className={`w-full text-xs font-bold py-2.5 px-4 rounded-lg text-white transition-all cursor-pointer shadow-lg ${
                isUploading
                  ? "bg-purple-800/50 cursor-not-allowed"
                  : "bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-purple-950/20"
              }`}
            >
              {isUploading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Indexing...
                </span>
              ) : (
                "⚡ Index Documents"
              )}
            </button>
          )}

          {/* Upload Feedback */}
          {uploadFeedback && (
            <div
              className={`mt-2 p-2.5 rounded-lg border text-xs flex gap-2 items-start transition-colors ${
                uploadFeedback.success
                  ? "bg-emerald-950/20 border-emerald-500/20 text-emerald-400"
                  : "bg-rose-950/20 border-rose-500/20 text-rose-400"
              }`}
            >
              <span className="font-medium">{uploadFeedback.message}</span>
            </div>
          )}
        </div>

        <div className={`border-t my-4 ${theme === "dark" ? "border-purple-500/10" : "border-purple-500/20"}`} />

        {/* Database Stats Card */}
        <div className={`border rounded-xl p-4 mb-4 transition-colors duration-300 ${
          theme === "dark" ? "bg-[#141021] border-purple-500/15" : "bg-white border-purple-200"
        }`}>
          <span className={`block text-[10px] font-bold uppercase tracking-wider mb-1 ${theme === "dark" ? "text-purple-400" : "text-purple-700"}`}>ChromaDB Status</span>
          <div className={`text-2xl font-extrabold tracking-tight ${theme === "dark" ? "text-[#c084fc]" : "text-purple-800"}`}>{chunkCount}</div>
          <span className={theme === "dark" ? "text-zinc-400" : "text-zinc-600"}>Total Text Chunks Persisted</span>
        </div>

        {/* Reset Panel */}
        <button
          onClick={resetDatabase}
          className={`w-full text-xs font-bold border py-2 rounded-lg transition-all cursor-pointer flex items-center justify-center gap-1.5 ${
            theme === "dark" 
              ? "border-rose-500/20 text-rose-400 hover:bg-rose-950/10" 
              : "border-rose-500/30 text-rose-600 hover:bg-rose-50"
          }`}
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          Wipe Database
        </button>
      </aside>

      {/* ---------------------------------------------------------------------
          Main Chat Workspace
          --------------------------------------------------------------------- */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        {/* Background glow effects */}
        {theme === "dark" && (
          <>
            <div className="absolute top-0 right-0 w-96 h-96 bg-purple-600/5 rounded-full blur-[120px] pointer-events-none" />
            <div className="absolute bottom-0 left-0 w-96 h-96 bg-indigo-600/5 rounded-full blur-[120px] pointer-events-none" />
          </>
        )}

        {/* App Title Header */}
        <header className={`h-16 border-b px-8 flex items-center justify-between shrink-0 backdrop-blur-md z-10 transition-colors duration-300 ${
          theme === "dark" ? "border-purple-500/10 bg-[#0c0a12]/80" : "border-purple-500/20 bg-white/80"
        }`}>
          <div>
            <h2 className={`text-md font-bold tracking-wide transition-colors duration-300 ${theme === "dark" ? "text-white" : "text-zinc-800"}`}>
              Local RAG Agent Canvas
            </h2>
            <p className={`text-[10px] font-medium transition-colors duration-300 ${theme === "dark" ? "text-zinc-400" : "text-zinc-600"}`}>
              Verify your local RAG Q&A interface in real time
            </p>
          </div>
          
          {/* Light/Dark Toggle Switch */}
          <button
            onClick={() => setTheme(prev => prev === "dark" ? "light" : "dark")}
            className={`p-2 rounded-lg border transition-all cursor-pointer flex items-center gap-1.5 text-xs font-semibold ${
              theme === "dark" 
                ? "bg-[#141021] border-purple-500/20 text-purple-300 hover:bg-[#1a162b]" 
                : "bg-purple-100/50 border-purple-500/30 text-purple-800 hover:bg-purple-100"
            }`}
          >
            {theme === "dark" ? (
              <>
                <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707-.707M12 8a4 4 0 100 8 4 4 0 000-8z" />
                </svg>
                <span>Light Mode</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                </svg>
                <span>Dark Mode</span>
              </>
            )}
          </button>
        </header>

        {/* Chat History Area */}
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center max-w-xl mx-auto text-center space-y-6">
              <div>
                <h3 className="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-[#c084fc] to-[#7c3aed] mb-2">
                  Ground Your Conversations
                </h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Index documents in the sidebar, then ask questions. The agent will retrieve facts from ChromaDB and compile answers grounded strictly in your context.
                </p>
              </div>

              {/* Sample Prompts */}
              <div className="grid grid-cols-2 gap-3 w-full">
                {[
                  "What is Model Context Protocol?",
                  "Key features of MCP servers",
                  "Explain embeddings simply",
                  "Clear database sample stats",
                ].map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => sendQuestion(prompt)}
                    className={`text-left text-xs p-4 rounded-xl border transition-all cursor-pointer font-medium group ${
                      theme === "dark"
                        ? "bg-[#141021]/80 hover:bg-[#1a162b] border-purple-500/10 hover:border-purple-500/30 text-zinc-300"
                        : "bg-white hover:bg-purple-50/50 border-purple-200 text-zinc-700 hover:border-purple-300 shadow-sm"
                    }`}
                  >
                    <span>{prompt}</span>
                    <span className="block text-[10px] text-purple-400 font-medium mt-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      Send Prompt &rarr;
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-6">
              {messages.map((message, idx) => (
                <div key={idx} className={`flex flex-col ${message.role === "user" ? "items-end" : "items-start"}`}>
                  <div className={`flex items-center gap-2 mb-1.5 text-[10px] font-semibold uppercase tracking-wider transition-colors ${
                    theme === "dark" ? "text-zinc-400" : "text-zinc-600"
                  }`}>
                    {message.role === "user" ? "You" : "RAG Agent"}
                  </div>
                  
                  {/* Conflict Warning Card */}
                  {message.role === "assistant" && message.conflict && (
                    <div className={`mb-3 p-4 rounded-xl border flex gap-3 transition-colors duration-300 w-full max-w-[85%] ${
                      theme === "dark"
                        ? "bg-amber-500/10 border-amber-500/20 text-amber-200"
                        : "bg-amber-50 border-amber-300 text-amber-900 shadow-sm shadow-amber-500/5"
                    }`}>
                      <div className="flex-shrink-0 text-lg">⚠️</div>
                      <div>
                        <h4 className="font-bold text-xs uppercase tracking-wider mb-1">Factual Mismatch Detected</h4>
                        <p className="text-sm font-medium leading-relaxed whitespace-pre-wrap">{message.conflict}</p>
                      </div>
                    </div>
                  )}

                  {/* Message bubble */}
                  <div
                    className={`text-sm leading-relaxed p-4 rounded-2xl max-w-[85%] shadow-md transition-colors duration-300 ${
                      message.role === "user"
                        ? "bg-gradient-to-br from-purple-600 to-indigo-600 text-white rounded-br-none"
                        : theme === "dark"
                          ? "bg-[#141021]/60 border border-purple-500/10 text-zinc-100 rounded-bl-none backdrop-blur-sm"
                          : "bg-white border border-purple-200 text-zinc-800 rounded-bl-none shadow-sm shadow-purple-500/5"
                    }`}
                  >
                    {message.role === "user" ? (
                      message.content
                    ) : (
                      <MarkdownContent 
                        content={
                          message.conflict 
                            ? message.content.replace(message.conflict, "").trim() 
                            : message.content
                        } 
                        theme={theme} 
                      />
                    )}

                    {/* Meta info for bot */}
                    {message.role === "assistant" && message.model && (
                      <div className={`mt-3.5 border-t pt-1.5 flex gap-3 text-[10px] font-medium transition-colors ${
                        theme === "dark" ? "border-purple-500/10 text-purple-400" : "border-purple-200 text-purple-700"
                      }`}>
                        <span>Model: {message.model}</span>
                        {message.tokens && <span>Tokens: {message.tokens}</span>}
                      </div>
                    )}
                  </div>

                  {/* Grounded References / Sources */}
                  {message.role === "assistant" && message.sources && message.sources.length > 0 && (
                    <div className="w-[85%] mt-2">
                      <button
                        onClick={() => toggleSources(idx)}
                        className={`text-xs font-bold flex items-center gap-1 cursor-pointer transition-colors ${
                          theme === "dark" ? "text-purple-400 hover:text-purple-300" : "text-purple-700 hover:text-purple-600"
                        }`}
                      >
                        <svg
                          className={`w-3.5 h-3.5 transition-transform ${expandedSources[idx] ? "rotate-180" : ""}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M19 9l-7 7-7-7" />
                        </svg>
                        {expandedSources[idx] ? "Hide Citations" : `View Citations (${message.sources.length})`}
                      </button>

                      {expandedSources[idx] && (
                        <div className="mt-2 space-y-2">
                          {message.sources.map((src, sIdx) => (
                            <div
                              key={sIdx}
                              className={`border-l-2 p-3 rounded-r-lg border transition-colors ${
                                theme === "dark"
                                  ? "border-purple-500 bg-purple-950/5 border-y-purple-500/5 border-r-purple-500/5 text-zinc-300"
                                  : "border-purple-500 bg-purple-50/50 border-y-purple-200 border-r-purple-200 text-zinc-700 shadow-sm"
                              }`}
                            >
                              <div className={`flex justify-between items-center font-bold text-[10px] mb-1 transition-colors ${
                                theme === "dark" ? "text-purple-300" : "text-purple-800"
                              }`}>
                                <span>
                                  [{sIdx + 1}]{" "}
                                  {src.source.startsWith("http://") || src.source.startsWith("https://") ? (
                                    <a
                                      href={src.source}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className={`underline break-all ${
                                        theme === "dark" ? "text-purple-400 hover:text-purple-300" : "text-purple-700 hover:text-purple-600"
                                      }`}
                                    >
                                      {src.source}
                                    </a>
                                  ) : (
                                    src.source
                                  )}
                                </span>
                                <span>Relevance: {(src.score * 100).toFixed(1)}%</span>
                              </div>
                              <div className={`leading-relaxed font-sans mt-1 transition-colors ${
                                theme === "dark" ? "text-zinc-400" : "text-zinc-600"
                              }`}>
                                {src.text}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {/* Bot typing state spinner */}
              {isGenerating && (
                <div className="flex flex-col items-start">
                  <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1.5 transition-colors ${
                    theme === "dark" ? "text-zinc-400" : "text-zinc-600"
                  }`}>
                    RAG Agent
                  </div>
                  <div className={`p-4 rounded-2xl rounded-bl-none flex items-center gap-2 backdrop-blur-sm border transition-colors duration-300 ${
                    theme === "dark" ? "bg-[#141021]/60 border-purple-500/10" : "bg-white border-purple-200"
                  }`}>
                    <span className="flex h-2 w-2 relative">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500"></span>
                    </span>
                    <span className="flex h-2 w-2 relative animate-delay-100">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500"></span>
                    </span>
                    <span className="flex h-2 w-2 relative animate-delay-200">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500"></span>
                    </span>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Chat Input Dock */}
        <div className={`p-8 shrink-0 transition-colors duration-300 ${
          theme === "dark" 
            ? "bg-gradient-to-t from-[#0c0a12] via-[#0c0a12]/90 to-transparent" 
            : "bg-gradient-to-t from-[#f8f6fc] via-[#f8f6fc]/90 to-transparent"
        }`}>
          <div className="max-w-3xl mx-auto relative">
            <textarea
              rows={1}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendQuestion();
                }
              }}
              placeholder={chunkCount === 0 ? "Upload documents first to activate chat..." : "Ask a question about your documents..."}
              disabled={chunkCount === 0 || isGenerating}
              className={`w-full rounded-xl py-4 pl-4 pr-14 text-sm resize-none max-h-40 min-h-[52px] focus:outline-none focus:ring-1 focus:ring-purple-500/30 transition-all duration-300 ${
                chunkCount === 0 
                  ? "cursor-not-allowed opacity-50" 
                  : ""
              } ${
                theme === "dark"
                  ? "bg-[#141021]/80 hover:bg-[#1a162b]/80 focus:bg-[#1a162b] border border-purple-500/15 focus:border-purple-500/40 text-zinc-100 placeholder-zinc-500"
                  : "bg-white hover:bg-zinc-50 focus:bg-white border border-purple-200 focus:border-purple-500 text-zinc-800 placeholder-zinc-400"
              }`}
            />
            <button
              onClick={() => sendQuestion()}
              disabled={!query.trim() || isGenerating || chunkCount === 0}
              className={`absolute right-3.5 top-3.5 p-1.5 rounded-lg text-white transition-all cursor-pointer ${
                query.trim() && !isGenerating && chunkCount > 0
                  ? "bg-purple-600 hover:bg-purple-500"
                  : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
              }`}
            >
              <svg className="w-4.5 h-4.5" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
