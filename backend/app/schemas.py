"""Skill 广场与调用相关 Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatParams(BaseModel):
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, alias="maxTokens", ge=1, le=32768)

    model_config = {"populate_by_name": True}


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    specialty: str = Field(default="", max_length=64)
    router_blurb: str = Field(default="", max_length=256, alias="routerBlurb")
    triggers: list[str] = Field(default_factory=list)
    model: str = Field(min_length=1, max_length=128)
    system_prompt: str = Field(alias="systemPrompt")
    user_prompt: str = Field(alias="userPrompt")
    params: ChatParams = Field(default_factory=ChatParams)
    tags: list[str] = Field(default_factory=list)
    visibility: Literal["private", "team", "public"] = "private"
    examples: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class AgentBuildRequest(AgentCreate):
    pass


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    specialty: Optional[str] = Field(default=None, max_length=64)
    router_blurb: Optional[str] = Field(default=None, max_length=256, alias="routerBlurb")
    triggers: Optional[list[str]] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = Field(default=None, alias="systemPrompt")
    user_prompt: Optional[str] = Field(default=None, alias="userPrompt")
    params: Optional[ChatParams] = None
    tags: Optional[list[str]] = None
    visibility: Optional[Literal["private", "team", "public"]] = None
    examples: Optional[list[dict[str, Any]]] = None
    md_doc: Optional[str] = Field(default=None, alias="mdDoc")
    workflow: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class AgentPublishRequest(BaseModel):
    changelog: str = "初始版本"
    version: Optional[str] = None
    visibility: Optional[Literal["private", "team", "public"]] = None
    optimize: bool = True


class AgentPublishToPlazaRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = ""
    specialty: str = Field(min_length=1, max_length=64)
    model: str
    system_prompt: str = Field(default="", alias="systemPrompt")
    user_prompt: str = Field(default="", alias="userPrompt")
    intent: str = ""
    params: ChatParams = Field(default_factory=ChatParams)
    tags: list[str] = Field(default_factory=list)
    visibility: Literal["team", "public"] = "team"
    changelog: str = ""
    examples: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class AgentPublicOut(BaseModel):
    id: str
    name: str
    description: str
    specialty: str = ""
    category: str = ""
    category_name: str = Field(default="", alias="categoryName")
    router_blurb: str = Field(default="", alias="routerBlurb")
    triggers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    author_name: str = Field(alias="authorName")
    version: str
    changelog: str = ""
    status: str
    visibility: str
    md_doc: str = Field(default="", alias="mdDoc")
    variables: list[Any] = Field(default_factory=list)
    examples: list[Any] = Field(default_factory=list)
    total_calls: int = Field(default=0, alias="totalCalls")
    published_at: Optional[datetime] = Field(default=None, alias="publishedAt")

    model_config = {"populate_by_name": True}


class AgentOwnerOut(AgentPublicOut):
    model_name: str = Field(alias="modelName")
    model_params: dict[str, Any] = Field(default_factory=dict, alias="modelParams")
    system_prompt: str = Field(alias="systemPrompt")
    user_prompt_template: str = Field(alias="userPromptTemplate")
    workflow: dict[str, Any] = Field(default_factory=dict)


class AgentPlazaItem(BaseModel):
    id: str
    name: str
    description: str
    specialty: str = ""
    category: str = ""
    category_name: str = Field(default="", alias="categoryName")
    router_blurb: str = Field(default="", alias="routerBlurb")
    triggers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    author_name: str = Field(alias="authorName")
    version: str
    changelog: str = ""
    status: str
    visibility: str
    examples: list[Any] = Field(default_factory=list)
    total_calls: int = Field(default=0, alias="totalCalls")
    published_at: Optional[datetime] = Field(default=None, alias="publishedAt")
    is_mine: bool = Field(default=False, alias="isMine")

    model_config = {"populate_by_name": True}


class AgentCallRequest(BaseModel):
    variables: dict[str, str] = Field(default_factory=dict)
    session_id: Optional[str] = Field(default=None, alias="sessionId")

    model_config = {"populate_by_name": True}


class AgentCallResponse(BaseModel):
    output: str
    latency_ms: int = Field(alias="latencyMs")
    agent_version: str = Field(alias="agentVersion")
    tool_trace: Optional[dict[str, Any]] = Field(default=None, alias="toolTrace")
    resolved_skill_id: Optional[str] = Field(default=None, alias="resolvedSkillId")
    resolved_skill_name: Optional[str] = Field(default=None, alias="resolvedSkillName")

    model_config = {"populate_by_name": True}


class SkillResolveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=10, alias="topK")
    recall_k: int = Field(default=8, ge=1, le=20, alias="recallK")
    rerank: bool = True

    model_config = {"populate_by_name": True}


class SkillResolveItem(BaseModel):
    skill_id: str = Field(alias="skillId")
    name: str
    specialty: str = ""
    confidence: float = 0.0
    reason: str = ""

    model_config = {"populate_by_name": True}


class SkillResolveResponse(BaseModel):
    query: str
    skills: list[SkillResolveItem]
    skill_id: Optional[str] = Field(default=None, alias="skillId")
    confidence: Optional[float] = None

    model_config = {"populate_by_name": True}
