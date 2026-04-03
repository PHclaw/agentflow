import React, { useState, useRef } from 'react'
import { useParams } from 'react-router-dom'
import { knowledge } from '../services/api'

interface Document {
  id: string
  filename: string
  size: number
  status: 'pending' | 'processing' | 'ready' | 'failed'
  chunks_count: number
  created_at: string
}

export default function KnowledgeBase() {
  const { id } = useParams<{ id: string }>()
  const [documents, setDocuments] = useState<Document[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    if (!id) return

    setUploading(true)

    try {
      for (const file of Array.from(files)) {
        const newDoc: Document = {
          id: Date.now().toString(),
          filename: file.name,
          size: file.size,
          status: 'pending',
          chunks_count: 0,
          created_at: new Date().toISOString(),
        }
        setDocuments((prev) => [...prev, newDoc])

        await knowledge.upload(id, file)
        
        setDocuments((prev) =>
          prev.map((d) =>
            d.id === newDoc.id ? { ...d, status: 'ready' as const, chunks_count: 10 } : d
          )
        )
      }
    } catch (error) {
      console.error('Upload failed:', error)
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFileSelect(e.dataTransfer.files)
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">知识库管理</h2>
        <p className="text-gray-500">上传文档，构建你的专属知识库</p>
      </div>

      {/* Upload Area */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition ${
          dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx,.txt,.md,.csv,.xlsx"
          onChange={(e) => handleFileSelect(e.target.files)}
          className="hidden"
        />
        
        <div className="text-5xl mb-4">📤</div>
        <h3 className="text-lg font-semibold text-gray-700 mb-2">
          {uploading ? '上传中...' : '拖拽文件到此处上传'}
        </h3>
        <p className="text-gray-500 text-sm">
          支持 PDF、Word、Excel、TXT、Markdown 等格式
        </p>
      </div>

      {/* Supported Formats */}
      <div className="mt-6 p-4 bg-gray-50 rounded-lg">
        <h4 className="font-medium text-gray-700 mb-2">支持的文件格式</h4>
        <div className="flex flex-wrap gap-2">
          {['PDF', 'Word', 'Excel', 'TXT', 'Markdown', 'CSV'].map((format) => (
            <span key={format} className="px-2 py-1 bg-white border rounded text-sm text-gray-600">
              {format}
            </span>
          ))}
        </div>
      </div>

      {/* Document List */}
      {documents.length > 0 && (
        <div className="mt-8">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            已上传文档 ({documents.length})
          </h3>
          <div className="space-y-3">
            {documents.map((doc) => (
              <div key={doc.id} className="bg-white border rounded-lg p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-xl">📄</div>
                  <div>
                    <h4 className="font-medium text-gray-900">{doc.filename}</h4>
                    <p className="text-sm text-gray-500">
                      {formatSize(doc.size)} · {doc.chunks_count} 个知识块
                    </p>
                  </div>
                </div>
                <StatusBadge status={doc.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: Document['status'] }) {
  const config: Record<string, { label: string; className: string }> = {
    pending: { label: '等待中', className: 'bg-gray-100 text-gray-600' },
    processing: { label: '处理中', className: 'bg-yellow-100 text-yellow-600' },
    ready: { label: '已就绪', className: 'bg-green-100 text-green-600' },
    failed: { label: '失败', className: 'bg-red-100 text-red-600' },
  }

  const { label, className } = config[status] || config.pending

  return (
    <span className={`px-2 py-1 text-xs rounded-full ${className}`}>
      {label}
    </span>
  )
}
