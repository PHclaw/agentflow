import React, { useState, useEffect, useCallback } from 'react'
import {
  Plus,
  Search,
  Upload,
  FileText,
  File,
  X,
  Download,
  Trash2,
  Eye,
  MoreVertical,
  BookOpen,
  Layers,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  Grid,
  List,
  RefreshCw,
  Settings,
  FolderOpen,
} from 'lucide-react'
import { api } from '../services/api'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Card } from '../components/ui/Card'
import { Modal, ConfirmModal } from '../components/ui/Modal'

interface KnowledgeBase {
  id: string
  name: string
  description: string
  document_count: number
  chunk_count: number
  created_at: string
  updated_at: string
  status: 'ready' | 'indexing' | 'error'
}

interface Document {
  id: number
  name: string
  type: string
  size: number
  chunks: number
  status: 'completed' | 'processing' | 'failed'
  created_at: string
}

export default function KnowledgePage() {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedKB, setSelectedKB] = useState<KnowledgeBase | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newKBName, setNewKBName] = useState('')
  const [newKBDescription, setNewKBDescription] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

  useEffect(() => {
    loadKnowledgeBases()
  }, [])

  const loadKnowledgeBases = async () => {
    try {
      setLoading(true)
      const response = await api.get('/knowledge')
      setKnowledgeBases(response.data?.knowledge_bases || [])
    } catch (error) {
      // 使用模拟数据
      setKnowledgeBases([
        {
          id: '1',
          name: '产品文档',
          description: '公司产品使用文档和技术规格',
          document_count: 25,
          chunk_count: 1250,
          created_at: '2024-01-15T10:30:00Z',
          updated_at: '2024-01-20T15:45:00Z',
          status: 'ready',
        },
        {
          id: '2',
          name: 'FAQ 知识库',
          description: '常见问题解答',
          document_count: 45,
          chunk_count: 890,
          created_at: '2024-01-10T09:00:00Z',
          updated_at: '2024-01-19T11:20:00Z',
          status: 'ready',
        },
        {
          id: '3',
          name: '培训材料',
          description: '员工培训资料',
          document_count: 12,
          chunk_count: 450,
          created_at: '2024-01-05T14:00:00Z',
          updated_at: '2024-01-18T09:30:00Z',
          status: 'indexing',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  const loadDocuments = async (kbId: string) => {
    try {
      const response = await api.get(`/knowledge/${kbId}/documents`)
      setDocuments(response.data?.documents || [])
    } catch (error) {
      // 使用模拟数据
      setDocuments([
        {
          id: 1,
          name: '产品使用手册.pdf',
          type: 'pdf',
          size: 2.5 * 1024 * 1024,
          chunks: 45,
          status: 'completed',
          created_at: '2024-01-15T10:30:00Z',
        },
        {
          id: 2,
          name: 'API接口文档.docx',
          type: 'docx',
          size: 1.2 * 1024 * 1024,
          chunks: 28,
          status: 'completed',
          created_at: '2024-01-14T09:00:00Z',
        },
        {
          id: 3,
          name: '常见问题.md',
          type: 'md',
          size: 156 * 1024,
          chunks: 12,
          status: 'processing',
          created_at: '2024-01-13T14:00:00Z',
        },
      ])
    }
  }

  const handleCreateKB = async () => {
    if (!newKBName.trim()) return
    
    try {
      await api.post('/knowledge', {
        name: newKBName,
        description: newKBDescription,
      })
      setShowCreateModal(false)
      setNewKBName('')
      setNewKBDescription('')
      loadKnowledgeBases()
    } catch (error) {
      console.error('Failed to create KB:', error)
    }
  }

  const handleFileUpload = async (files: FileList) => {
    if (!selectedKB || files.length === 0) return

    setUploading(true)
    setUploadProgress(0)

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        
        // 模拟上传进度
        for (let progress = 0; progress <= 100; progress += 10) {
          setUploadProgress(progress)
          await new Promise(resolve => setTimeout(resolve, 100))
        }

        await api.upload(`/knowledge/${selectedKB.id}/documents`, file)
      }

      loadDocuments(selectedKB.id)
      setShowUploadModal(false)
    } catch (error) {
      console.error('Upload failed:', error)
    } finally {
      setUploading(false)
      setUploadProgress(0)
    }
  }

  const handleSelectKB = (kb: KnowledgeBase) => {
    setSelectedKB(kb)
    loadDocuments(kb.id)
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const getFileIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'pdf':
        return <FileText className="w-5 h-5 text-red-500" />
      case 'docx':
      case 'doc':
        return <File className="w-5 h-5 text-blue-500" />
      case 'txt':
      case 'md':
        return <FileText className="w-5 h-5 text-slate-500" />
      default:
        return <File className="w-5 h-5 text-slate-400" />
    }
  }

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            知识库管理
          </h1>
          <p className="mt-1 text-slate-500 dark:text-slate-400">
            上传和管理您的知识文档
          </p>
        </div>
        <Button leftIcon={<Plus className="w-4 h-4" />} onClick={() => setShowCreateModal(true)}>
          创建知识库
        </Button>
      </div>

      <div className="flex gap-6">
        {/* Left sidebar - Knowledge Bases */}
        <div className="w-80 flex-shrink-0">
          <Card className="p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-slate-900 dark:text-white">
                知识库列表
              </h2>
              <button
                onClick={loadKnowledgeBases}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>

            <div className="relative mb-4">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <input
                type="text"
                placeholder="搜索知识库..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white text-sm"
              />
            </div>

            <div className="space-y-2">
              {knowledgeBases
                .filter(kb => kb.name.toLowerCase().includes(searchQuery.toLowerCase()))
                .map((kb) => (
                  <button
                    key={kb.id}
                    onClick={() => handleSelectKB(kb)}
                    className={`w-full p-3 rounded-xl text-left transition-colors ${
                      selectedKB?.id === kb.id
                        ? 'bg-indigo-50 dark:bg-indigo-900/30 border border-indigo-200 dark:border-indigo-800'
                        : 'hover:bg-slate-50 dark:hover:bg-slate-800'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`p-2 rounded-lg ${
                        selectedKB?.id === kb.id
                          ? 'bg-indigo-500'
                          : 'bg-slate-100 dark:bg-slate-700'
                      }`}>
                        <BookOpen className={`w-4 h-4 ${
                          selectedKB?.id === kb.id ? 'text-white' : 'text-slate-500'
                        }`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-slate-900 dark:text-white truncate">
                          {kb.name}
                        </p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          {kb.document_count} 个文档
                        </p>
                      </div>
                      {kb.status === 'ready' ? (
                        <CheckCircle className="w-4 h-4 text-emerald-500" />
                      ) : kb.status === 'indexing' ? (
                        <Loader2 className="w-4 h-4 text-amber-500 animate-spin" />
                      ) : (
                        <AlertCircle className="w-4 h-4 text-red-500" />
                      )}
                    </div>
                  </button>
                ))}
            </div>
          </Card>
        </div>

        {/* Main content - Documents */}
        <div className="flex-1">
          {selectedKB ? (
            <>
              {/* KB Header */}
              <Card className="p-6 mb-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                      {selectedKB.name}
                    </h2>
                    <p className="mt-1 text-slate-500 dark:text-slate-400">
                      {selectedKB.description}
                    </p>
                    <div className="flex items-center gap-6 mt-4 text-sm">
                      <div className="flex items-center gap-2 text-slate-500">
                        <Layers className="w-4 h-4" />
                        {selectedKB.document_count} 个文档
                      </div>
                      <div className="flex items-center gap-2 text-slate-500">
                        <FileText className="w-4 h-4" />
                        {selectedKB.chunk_count} 个知识块
                      </div>
                      <div className="flex items-center gap-2 text-slate-500">
                        <Clock className="w-4 h-4" />
                        更新于 {new Date(selectedKB.updated_at).toLocaleDateString('zh-CN')}
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      leftIcon={<Settings className="w-4 h-4" />}
                    >
                      设置
                    </Button>
                    <Button
                      size="sm"
                      leftIcon={<Upload className="w-4 h-4" />}
                      onClick={() => setShowUploadModal(true)}
                    >
                      上传文档
                    </Button>
                  </div>
                </div>
              </Card>

              {/* Documents */}
              {documents.length === 0 ? (
                <Card className="p-12 text-center">
                  <FolderOpen className="w-16 h-16 text-slate-300 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-2">
                    还没有文档
                  </h3>
                  <p className="text-slate-500 dark:text-slate-400 mb-6">
                    上传您的第一个文档开始构建知识库
                  </p>
                  <Button leftIcon={<Upload className="w-4 h-4" />} onClick={() => setShowUploadModal(true)}>
                    上传文档
                  </Button>
                </Card>
              ) : viewMode === 'grid' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {documents.map((doc) => (
                    <Card key={doc.id} className="p-4 hover:shadow-lg transition-shadow">
                      <div className="flex items-start gap-3">
                        <div className="p-3 rounded-xl bg-slate-100 dark:bg-slate-800">
                          {getFileIcon(doc.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-slate-900 dark:text-white truncate">
                            {doc.name}
                          </p>
                          <p className="text-sm text-slate-500 mt-1">
                            {formatFileSize(doc.size)} · {doc.chunks} 块
                          </p>
                        </div>
                        <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                          doc.status === 'completed'
                            ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                            : doc.status === 'processing'
                            ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                            : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        }`}>
                          {doc.status === 'completed' ? '就绪' : doc.status === 'processing' ? '处理中' : '失败'}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-100 dark:border-slate-800">
                        <button className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 text-sm">
                          <Eye className="w-4 h-4" />
                          预览
                        </button>
                        <button className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 text-sm">
                          <Download className="w-4 h-4" />
                          下载
                        </button>
                        <button className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 text-sm">
                          <Trash2 className="w-4 h-4" />
                          删除
                        </button>
                      </div>
                    </Card>
                  ))}
                </div>
              ) : (
                <Card className="overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-slate-50 dark:bg-slate-800/50">
                      <tr>
                        <th className="px-6 py-4 text-left text-sm font-medium text-slate-500 dark:text-slate-400">
                          文档
                        </th>
                        <th className="px-6 py-4 text-left text-sm font-medium text-slate-500 dark:text-slate-400">
                          大小
                        </th>
                        <th className="px-6 py-4 text-left text-sm font-medium text-slate-500 dark:text-slate-400">
                          知识块
                        </th>
                        <th className="px-6 py-4 text-left text-sm font-medium text-slate-500 dark:text-slate-400">
                          状态
                        </th>
                        <th className="px-6 py-4 text-right text-sm font-medium text-slate-500 dark:text-slate-400">
                          操作
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                      {documents.map((doc) => (
                        <tr key={doc.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              {getFileIcon(doc.type)}
                              <span className="font-medium text-slate-900 dark:text-white">
                                {doc.name}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-slate-500 dark:text-slate-400">
                            {formatFileSize(doc.size)}
                          </td>
                          <td className="px-6 py-4 text-slate-500 dark:text-slate-400">
                            {doc.chunks}
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                              doc.status === 'completed'
                                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                                : doc.status === 'processing'
                                ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                            }`}>
                              {doc.status === 'completed' ? '就绪' : doc.status === 'processing' ? '处理中' : '失败'}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex justify-end gap-1">
                              <button className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100">
                                <Eye className="w-4 h-4" />
                              </button>
                              <button className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100">
                                <Download className="w-4 h-4" />
                              </button>
                              <button className="p-2 rounded-lg text-red-500 hover:bg-red-50">
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Card>
              )}
            </>
          ) : (
            <Card className="p-12 text-center">
              <BookOpen className="w-16 h-16 text-slate-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-2">
                选择一个知识库
              </h3>
              <p className="text-slate-500 dark:text-slate-400">
                从左侧列表选择一个知识库来查看和管理文档
              </p>
            </Card>
          )}
        </div>
      </div>

      {/* Create KB Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="创建知识库"
        description="创建一个新的知识库来存储和管理您的文档"
      >
        <div className="space-y-4">
          <Input
            label="知识库名称"
            placeholder="输入知识库名称"
            value={newKBName}
            onChange={(e) => setNewKBName(e.target.value)}
          />
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">
              描述（可选）
            </label>
            <textarea
              value={newKBDescription}
              onChange={(e) => setNewKBDescription(e.target.value)}
              placeholder="描述这个知识库的用途"
              rows={3}
              className="w-full px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="outline" onClick={() => setShowCreateModal(false)}>
              取消
            </Button>
            <Button onClick={handleCreateKB} disabled={!newKBName.trim()}>
              创建
            </Button>
          </div>
        </div>
      </Modal>

      {/* Upload Modal */}
      <Modal
        isOpen={showUploadModal}
        onClose={() => !uploading && setShowUploadModal(false)}
        title="上传文档"
        description="支持 PDF、Word、文本等格式"
        size="lg"
      >
        <div className="space-y-4">
          <div
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
              uploading
                ? 'border-slate-300 bg-slate-50'
                : 'border-slate-300 dark:border-slate-600 hover:border-indigo-400 dark:hover:border-indigo-600'
            }`}
          >
            <input
              type="file"
              multiple
              accept=".pdf,.doc,.docx,.txt,.md,.csv"
              onChange={(e) => e.target.files && handleFileUpload(e.target.files)}
              disabled={uploading}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              {uploading ? (
                <>
                  <Loader2 className="w-12 h-12 text-indigo-500 mx-auto mb-4 animate-spin" />
                  <p className="text-slate-600 dark:text-slate-400">
                    上传中... {uploadProgress}%
                  </p>
                  <div className="w-full bg-slate-200 rounded-full h-2 mt-4 max-w-xs mx-auto">
                    <div
                      className="bg-indigo-500 h-2 rounded-full transition-all"
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                </>
              ) : (
                <>
                  <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400 mb-2">
                    拖拽文件到此处，或<span className="text-indigo-600">点击上传</span>
                  </p>
                  <p className="text-sm text-slate-400">
                    支持 PDF, DOC, DOCX, TXT, MD, CSV（最大 50MB）
                  </p>
                </>
              )}
            </label>
          </div>

          <div className="text-sm text-slate-500 dark:text-slate-400">
            <p className="font-medium mb-2">上传提示：</p>
            <ul className="list-disc list-inside space-y-1">
              <li>文档将自动进行分块和向量化处理</li>
              <li>建议单个文档不超过 50MB</li>
              <li>PDF 和 Word 文档将自动提取文本内容</li>
            </ul>
          </div>
        </div>
      </Modal>
    </div>
  )
}
