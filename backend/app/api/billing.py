"""
支付 API - Stripe 集成
"""
import stripe
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from ..core.config import settings
from ..core.database import get_db
from ..models.user import User
from ..models.subscription import Subscription, PlanType

router = APIRouter(prefix="/api/billing", tags=["billing"])

# 初始化 Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


# 定价计划
PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "agents": 1,
        "messages": 100,
        "features": ["1个Agent", "100条消息/月", "基础模板"]
    },
    "pro": {
        "name": "Pro",
        "price": 29,
        "price_id": settings.STRIPE_PRICE_PRO,
        "agents": 5,
        "messages": 5000,
        "features": ["5个Agent", "5000条消息/月", "高级模板", "知识库", "优先支持"]
    },
    "team": {
        "name": "Team",
        "price": 99,
        "price_id": settings.STRIPE_PRICE_TEAM,
        "agents": 20,
        "messages": 50000,
        "features": ["20个Agent", "50000条消息/月", "全部功能", "团队协作", "专属客服"]
    }
}


class CreateCheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class CreatePortalRequest(BaseModel):
    return_url: str


@router.get("/plans")
async def get_plans():
    """获取定价计划"""
    return {
        "plans": PLANS,
        "current_plan": None  # 前端会根据用户状态显示
    }


@router.post("/checkout")
async def create_checkout_session(
    data: CreateCheckoutRequest,
    db: Session = Depends(get_db),
    # user: User = Depends(get_current_user)  # TODO: 添加认证
):
    """创建 Stripe Checkout Session"""
    if not settings.STRIPE_SECRET_KEY:
        # 测试模式：返回模拟 session
        return {
            "url": data.success_url + "?test=1",
            "session_id": "cs_test_" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
        }
    
    # 获取或创建 Stripe 客户
    # customer = await get_or_create_stripe_customer(user, db)
    
    try:
        session = stripe.checkout.Session.create(
            # customer=customer.stripe_customer_id,
            mode="subscription",
            line_items=[{
                "price": data.price_id,
                "quantity": 1
            }],
            success_url=data.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=data.cancel_url,
            metadata={
                "user_id": "test_user"  # user.id
            }
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/portal")
async def create_portal_session(
    data: CreatePortalRequest,
    db: Session = Depends(get_db),
    # user: User = Depends(get_current_user)
):
    """创建客户门户 Session（管理订阅）"""
    if not settings.STRIPE_SECRET_KEY:
        return {"url": data.return_url}
    
    # customer = await get_or_create_stripe_customer(user, db)
    
    try:
        session = stripe.billing_portal.Session.create(
            customer="cus_test",  # customer.stripe_customer_id
            return_url=data.return_url
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """处理 Stripe Webhook"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        if settings.STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        else:
            event = stripe.Event.construct_from(
                json.loads(payload), stripe.api_key
            )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    
    # 处理事件
    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})
    
    if event_type == "checkout.session.completed":
        # 订阅创建成功
        user_id = data.get("metadata", {}).get("user_id")
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")
        
        # 更新用户订阅状态
        # await update_subscription(user_id, subscription_id, customer_id, db)
        
    elif event_type == "customer.subscription.updated":
        # 订阅更新
        subscription_id = data.get("id")
        status = data.get("status")
        
        # sub = db.query(Subscription).filter_by(stripe_subscription_id=subscription_id).first()
        # if sub:
        #     sub.status = status
        #     db.commit()
        
    elif event_type == "customer.subscription.deleted":
        # 订阅取消
        subscription_id = data.get("id")
        
        # sub = db.query(Subscription).filter_by(stripe_subscription_id=subscription_id).first()
        # if sub:
        #     sub.status = "canceled"
        #     sub.plan = PlanType.FREE.value
        #     db.commit()
    
    return {"received": True}


@router.get("/subscription")
async def get_subscription(
    db: Session = Depends(get_db),
    # user: User = Depends(get_current_user)
):
    """获取当前订阅状态"""
    # 测试模式返回模拟数据
    return {
        "plan": "free",
        "status": "active",
        "agents_used": 0,
        "messages_used": 0,
        "agents_limit": settings.FREE_AGENTS,
        "messages_limit": settings.FREE_MESSAGES
    }
