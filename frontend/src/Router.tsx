import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import App from './App'
import AgentList from './components/AgentList'
import WorkflowBuilder from './components/WorkflowBuilder'
import TemplateMarket from './pages/TemplateMarket'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import ChatPage from './pages/ChatPage'

export default function Router() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/templates" element={<TemplateMarket />} />
        <Route path="/agents" element={<AgentList />} />
        <Route path="/agents/:id/edit" element={<WorkflowBuilder />} />
        <Route path="/agents/:id/chat" element={<ChatPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/dashboard" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  )
}
