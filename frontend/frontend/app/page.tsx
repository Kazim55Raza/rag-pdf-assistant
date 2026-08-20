'use client';

import { useState, useEffect, useRef } from 'react';
import { supabase } from '@/lib/supabase';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';

export default function Dashboard() {
  const [user, setUser] = useState<any>(null);
  const [email, setEmail] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [documents, setDocuments] = useState<any[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  // Chat States
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<{ role: string; content: string; sources?: any[] }[]>([]);
  const [loadingAnswer, setLoadingAnswer] = useState(false);

  // Auto-scroll Ref
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 1. Auto-scroll to bottom whenever messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 2. Auth Session Management
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    const { error } = await supabase.auth.signInWithOtp({ email });
    if (error) alert(error.message);
    else alert('Check your email for the magic login link!');
  };

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      if (session?.user) fetchDocuments(session.user.id);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      if (session?.user) fetchDocuments(session.user.id);
    });

    return () => subscription.unsubscribe();
  }, []);

  // 3. Fetch User Documents
  const fetchDocuments = async (userId: string) => {
    const { data } = await supabase.from('documents').select('*').eq('user_id', userId);
    if (data) setDocuments(data);
  };

  // 4. Upload File to Backend
  const handleUpload = async () => {
    if (!file || !user) return;
    setUploading(true);

    try {
      const { data: docRecord, error } = await supabase
        .from('documents')
        .insert([{ user_id: user.id, filename: file.name, file_path: '', file_size: file.size, status: 'processing' }])
        .select()
        .single();

      if (error) throw error;

      const formData = new FormData();
      formData.append('file', file);
      formData.append('user_id', user.id);
      formData.append('document_id', docRecord.id);

      await axios.post(`${process.env.NEXT_PUBLIC_FASTAPI_URL}/api/process`, formData);

      alert('Document processed and indexed successfully!');
      fetchDocuments(user.id);
      setSelectedDocId(docRecord.id);
    } catch (err: any) {
      alert(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  // 5. Send Streaming Chat Query (Fixed IMMUTABLE SSE Reader)
  const handleSendChat = async () => {
    if (!query || !selectedDocId || !user || loadingAnswer) return;

    const userQuery = query;
    setQuery('');

    // Append user query and fresh empty assistant bubble
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: userQuery },
      { role: 'assistant', content: '', sources: [] },
    ]);
    setLoadingAnswer(true);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_FASTAPI_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          document_id: selectedDocId,
          query: userQuery,
        }),
      });

      if (!response.ok) throw new Error('Stream request failed');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');
      if (!reader) return;

      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // Split on single newlines for robust SSE handling
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // keep last uncompleted segment in buffer

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;

          const rawData = trimmed.replace('data: ', '').trim();
          if (rawData === '[DONE]') break;

          try {
            const parsed = JSON.parse(rawData);

            if (parsed.type === 'sources') {
              // Immutable state update for sources
              setMessages((prev) => {
                if (prev.length === 0) return prev;
                const lastIdx = prev.length - 1;
                const updated = [...prev];
                updated[lastIdx] = {
                  ...updated[lastIdx],
                  sources: parsed.data,
                };
                return updated;
              });
            } else if (parsed.type === 'token') {
              // Immutable state update for token append (NO MUTATION)
              setMessages((prev) => {
                if (prev.length === 0) return prev;
                const lastIdx = prev.length - 1;
                const updated = [...prev];
                updated[lastIdx] = {
                  ...updated[lastIdx],
                  content: updated[lastIdx].content + parsed.data,
                };
                return updated;
              });
            }
          } catch (e) {
            // Ignore temporary partial JSON parse errors
          }
        }
      }
    } catch (err: any) {
      alert(`Chat Error: ${err.message}`);
    } finally {
      setLoadingAnswer(false);
    }
  };

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gray-900 text-white p-6">
        <form onSubmit={handleLogin} className="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-md space-y-4">
          <h1 className="text-2xl font-bold text-center">Login to RAG Dashboard</h1>
          <input
            type="email"
            placeholder="Enter your email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full p-3 rounded bg-gray-700 text-white border border-gray-600 focus:outline-none"
            required
          />
          <button type="submit" className="w-full bg-blue-600 hover:bg-blue-500 text-white py-3 rounded font-semibold">
            Send Magic Link
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="flex h-screen bg-gray-900 text-white">
      {/* Sidebar - Documents List & Upload */}
      <div className="w-1/3 border-r border-gray-800 p-6 flex flex-col space-y-6">
        <h2 className="text-xl font-bold">Your Documents</h2>

        <div className="space-y-3">
          <input
            type="file"
            accept=".pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 cursor-pointer"
          />
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="w-full bg-green-600 hover:bg-green-500 disabled:bg-gray-700 py-2 rounded font-semibold text-sm"
          >
            {uploading ? 'Processing PDF...' : 'Upload Document'}
          </button>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              onClick={() => {
                if (doc.status === 'failed') {
                  alert('This document failed to process and cannot be used for chat.');
                  return;
                }
                setSelectedDocId(doc.id);
              }}
              className={`p-3 rounded cursor-pointer border ${
                selectedDocId === doc.id ? 'bg-blue-900 border-blue-500' : 'bg-gray-800 border-gray-700'
              }`}
            >
              <p className="font-medium truncate">{doc.filename}</p>
              <span className={`text-xs ${doc.status === 'ready' ? 'text-green-400' : doc.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}`}>
                Status: {doc.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Workspace */}
      <div className="flex-1 flex flex-col justify-between p-6">
        {selectedDocId ? (
          <>
            {/* Scrollable Message History Container */}
            <div className="flex-1 overflow-y-auto space-y-4 pr-4">
              {messages.map((msg, idx) => {
                const isStreamingThisMessage =
                  msg.role === 'assistant' &&
                  idx === messages.length - 1 &&
                  loadingAnswer;

                return (
                  <div
                    key={idx}
                    className={`p-4 rounded-lg max-w-2xl ${
                      msg.role === 'user' ? 'bg-blue-600 ml-auto' : 'bg-gray-800'
                    }`}
                  >
                    <div className="text-gray-100 text-sm leading-relaxed">
                      <ReactMarkdown
                        components={{
                          h3: ({ node, ...props }) => (
                            <h3 className="text-lg font-bold text-blue-400 mt-3 mb-2 border-b border-gray-700 pb-1" {...props} />
                          ),
                          p: ({ node, ...props }) => <p className="mb-2 text-gray-200" {...props} />,
                          ul: ({ node, ...props }) => <ul className="list-disc list-inside space-y-1.5 my-2 pl-2" {...props} />,
                          li: ({ node, ...props }) => <li className="text-gray-200" {...props} />,
                          strong: ({ node, ...props }) => <strong className="font-semibold text-white" {...props} />,
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>

                      {/* Animated Cursor Symbol */}
                      {isStreamingThisMessage && (
                        <span className="inline-block ml-1 font-bold text-blue-400 animate-pulse">
                          ▋
                        </span>
                      )}
                    </div>

                    {/* {msg.sources && msg.sources.length > 0 && (
                      <div className="mt-3 text-xs text-gray-400 border-t border-gray-700 pt-2">
                        <p className="font-semibold">Sources:</p>
                        {msg.sources.map((s, i) => (
                          <span key={i} className="mr-2 inline-block bg-gray-700 px-2 py-1 rounded mt-1">
                            Page {s.page_number}
                          </span>
                        ))}
                      </div>
                    )} */}
                    {msg.sources && msg.sources.length > 0 && (
  <div className="mt-3 text-xs text-gray-400 border-t border-gray-700 pt-2">
    <p className="font-semibold">Sources:</p>
    {Array.from(new Set(msg.sources.map((s: any) => s.page_number))).map((pageNum, i) => (
      <span key={i} className="mr-2 inline-block bg-gray-700 px-2 py-1 rounded mt-1">
        Page {pageNum}
      </span>
    ))}
  </div>
)}
                  </div>
                );
              })}

              {/* Auto-scroll target */}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Form */}
            <div className="flex space-x-2 pt-4">
              <input
                type="text"
                placeholder="Ask a question about this document..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                disabled={loadingAnswer}
                className="flex-1 p-3 rounded bg-gray-800 border border-gray-700 text-white focus:outline-none disabled:opacity-50"
              />
              <button
                onClick={handleSendChat}
                disabled={loadingAnswer || !query}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 px-6 py-3 rounded font-semibold"
              >
                {loadingAnswer ? 'Generating...' : 'Send'}
              </button>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Select or upload a document on the left to start chatting.
          </div>
        )}
      </div>
    </main>
  );
}