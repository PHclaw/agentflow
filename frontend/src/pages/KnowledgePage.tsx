import React from 'react';
import KnowledgeManager from '../components/KnowledgeManager';

export default function KnowledgePage() {
  return (
    <div className="min-h-screen bg-gray-900">
      <header className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-xl font-bold">知识库管理</h1>
        <p className="text-gray-400 text-sm">上传文档，构建向量知识库</p>
      </header>
      <div className="h-[calc(100vh-80px)]">
        <KnowledgeManager />
      </div>
    </div>
  );
}
