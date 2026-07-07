import React, { useState, useEffect } from 'react';

interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  document_count: number;
  created_at: string;
}

interface Document {
  id: number;
  filename: string;
  file_type: string;
  chunk_count: number;
  status: string;
  created_at: string;
}

interface SearchResult {
  id: number;
  content: string;
  filename: string;
  score: number;
}

export default function KnowledgeManager() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [selectedKb, setSelectedKb] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  
  // 创建知识库表单
  const [showCreateKb, setShowCreateKb] = useState(false);
  const [newKbName, setNewKbName] = useState('');
  const [newKbDesc, setNewKbDesc] = useState('');

  useEffect(() => {
    loadKnowledgeBases();
  }, []);

  useEffect(() => {
    if (selectedKb) {
      loadDocuments(selectedKb);
    }
  }, [selectedKb]);

  const loadKnowledgeBases = async () => {
    try {
      const res = await fetch('/api/v1/knowledge');
      if (!res.ok) throw new Error('加载失败');
      const data = await res.json();
      setKnowledgeBases(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load knowledge bases:', err);
      setKnowledgeBases([]);
    }
  };

  const loadDocuments = async (kbId: string) => {
    try {
      const res = await fetch(`/api/v1/knowledge/${kbId}/documents`);
      if (!res.ok) throw new Error('加载失败');
      const data = await res.json();
      setDocuments(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load documents:', err);
      setDocuments([]);
    }
  };

  const createKnowledgeBase = async () => {
    if (!newKbName.trim()) return;

    try {
      const res = await fetch('/api/v1/knowledge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKbName, description: newKbDesc }),
      });
      
      if (res.ok) {
        setShowCreateKb(false);
        setNewKbName('');
        setNewKbDesc('');
        loadKnowledgeBases();
      } else {
        const error = await res.json().catch(() => ({ detail: '创建失败' }));
        alert(error.detail || '创建失败');
      }
    } catch (err) {
      console.error('Failed to create knowledge base:', err);
      alert('创建失败');
    }
  };

  const uploadDocument = async (kbId: string, file: File) => {
    setLoading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`/api/v1/knowledge/${kbId}/documents`, {
        method: 'POST',
        body: formData,
      });
      
      if (res.ok) {
        loadDocuments(kbId);
      } else {
        const error = await res.json().catch(() => ({ detail: '上传失败' }));
        alert(error.detail || '上传失败');
      }
    } catch (err) {
      console.error('Failed to upload document:', err);
      alert('上传失败');
    } finally {
      setLoading(false);
    }
  };

  const deleteDocument = async (kbId: string, docId: number) => {
    if (!confirm('确定删除此文档？')) return;

    try {
      const res = await fetch(`/api/v1/knowledge/${kbId}/documents/${docId}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        loadDocuments(kbId);
      }
    } catch (err) {
      console.error('Failed to delete document:', err);
    }
  };

  const searchKnowledge = async () => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    try {
      const res = await fetch('/api/v1/knowledge/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          kb_ids: selectedKb ? [selectedKb] : null,
          top_k: 5,
        }),
      });
      
      if (!res.ok) throw new Error('搜索失败');
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (err) {
      console.error('Failed to search:', err);
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex bg-gray-900">
      {/* 左侧 - 知识库列表 */}
      <div className="w-64 border-r border-gray-800 overflow-y-auto">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h2 className="font-semibold">知识库</h2>
          <button
            onClick={() => setShowCreateKb(true)}
            className="p-1 hover:bg-gray-800 rounded"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>
        </div>
        
        <div className="p-2">
          {knowledgeBases.map(kb => (
            <button
              key={kb.id}
              onClick={() => setSelectedKb(kb.id)}
              className={`w-full text-left p-3 rounded-lg transition ${
                selectedKb === kb.id 
                  ? 'bg-purple-600 text-white' 
                  : 'hover:bg-gray-800'
              }`}
            >
              <div className="font-medium truncate">{kb.name}</div>
              <div className="text-sm text-gray-400">
                {kb.document_count} 个文档
              </div>
            </button>
          ))}
          
          {knowledgeBases.length === 0 && (
            <div className="text-center text-gray-500 py-8">
              暂无知识库
            </div>
          )}
        </div>
      </div>

      {/* 右侧 - 内容区 */}
      <div className="flex-1 flex flex-col">
        {!selectedKb ? (
          // 未选择知识库
          <div className="flex-1 flex items-center justify-center text-gray-500">
            选择一个知识库或创建新的知识库
          </div>
        ) : (
          <>
            {/* 搜索栏 */}
            <div className="p-4 border-b border-gray-800">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && searchKnowledge()}
                  placeholder="搜索知识库内容..."
                  className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 focus:outline-none focus:border-purple-500"
                />
                <button
                  onClick={searchKnowledge}
                  disabled={loading}
                  className="px-6 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg font-medium disabled:opacity-50"
                >
                  {loading ? '搜索中...' : '搜索'}
                </button>
              </div>
            </div>

            {/* 搜索结果或文档列表 */}
            <div className="flex-1 overflow-y-auto p-4">
              {searchResults.length > 0 ? (
                // 显示搜索结果
                <div className="space-y-4">
                  <h3 className="text-lg font-semibold mb-4">搜索结果</h3>
                  {searchResults.map((result) => (
                    <div key={result.id} className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-purple-400">{result.filename}</span>
                        <span className="text-sm text-gray-500">相似度: {(result.score * 100).toFixed(1)}%</span>
                      </div>
                      <p className="text-gray-300">{result.content}</p>
                    </div>
                  ))}
                </div>
              ) : (
                // 显示文档列表
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">文档列表</h3>
                    <label className="px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg cursor-pointer">
                      上传文档
                      <input
                        type="file"
                        accept=".txt,.md,.pdf,.docx"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) uploadDocument(selectedKb, file);
                        }}
                        className="hidden"
                      />
                    </label>
                  </div>
                  
                  {documents.length > 0 ? (
                    <div className="space-y-2">
                      {documents.map(doc => (
                        <div key={doc.id} className="flex items-center justify-between p-4 bg-gray-800 rounded-xl border border-gray-700">
                          <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-gray-700 flex items-center justify-center">
                              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            </div>
                            <div>
                              <div className="font-medium">{doc.filename}</div>
                              <div className="text-sm text-gray-400">
                                {doc.file_type.toUpperCase()} · {doc.chunk_count} 个分块 · {doc.status === 'done' ? '已处理' : '处理中'}
                              </div>
                            </div>
                          </div>
                          <button
                            onClick={() => deleteDocument(selectedKb, doc.id)}
                            className="p-2 hover:bg-red-500/20 rounded-lg text-gray-400 hover:text-red-400"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center text-gray-500 py-12">
                      暂无文档，点击上方按钮上传
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* 创建知识库弹窗 */}
      {showCreateKb && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-2xl p-6 w-full max-w-md border border-gray-700">
            <h3 className="text-lg font-semibold mb-4">创建知识库</h3>
            
            <div className="space-y-4">
              <input
                type="text"
                value={newKbName}
                onChange={(e) => setNewKbName(e.target.value)}
                placeholder="知识库名称"
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-purple-500"
              />
              
              <textarea
                value={newKbDesc}
                onChange={(e) => setNewKbDesc(e.target.value)}
                placeholder="描述（可选）"
                rows={3}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-purple-500 resize-none"
              />
            </div>
            
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreateKb(false)}
                className="flex-1 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg"
              >
                取消
              </button>
              <button
                onClick={createKnowledgeBase}
                className="flex-1 py-2 bg-purple-600 hover:bg-purple-500 rounded-lg font-medium"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
