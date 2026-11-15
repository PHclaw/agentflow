"""
支付 API - Stripe 集成
"""
import stripe
import json
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.core.database import get_db
from app.api.auth import get_current_user_id

from ..core.config import settings
from ..models.user import User
from ..models.subscription import Subscription, PlanType
from ..services.entitlement import Resource, ensure_subscription, limits_for

router = APIRouter()

# 初始化 Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


# 定价计划
# 额度一律从 settings 取，不在这里写死：前端 SettingsPage 曾经把免费版写成
# 「3 个 Agent / 1000 条消息」，和配置里的 1 / 100 对不上，用户看到的额度
# 和实际能用的不是一回事。单一数据源才能避免这类三方不一致。
PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "agents": settings.FREE_AGENTS,
        "messages": settings.FREE_MESSAGES,
        "features": [
            f"{settings.FREE_AGENTS}个Agent",
            f"{settings.FREE_MESSAGES}条消息/月",
            "基础模板",
        ],
    },
    "pro": {
        "name": "Pro",
        "price": 29,
        "price_id": settings.STRIPE_PRICE_PRO,
        "agents": settings.PRO_AGENTS,
        "messages": settings.PRO_MESSAGES,
        "features": [
            f"{settings.PRO_AGENTS}个Agent",
            f"{settings.PRO_MESSAGES}条消息/月",
            "高级模板",
            "知识库",
            "优先支持",
        ],
    },
    "team": {
        "name": "Team",
        "price": 99,
        "price_id": settings.STRIPE_PRICE_TEAM,
        "agents": settings.TEAM_AGENTS,
        "messages": settings.TEAM_MESSAGES,
        "features": [
            f"{settings.TEAM_AGENTS}个Agent",
            f"{settings.TEAM_MESSAGES}条消息/月",
            "全部功能",
            "团队协作",
            "专属客服",
        ],
    },
}


class CreateCheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class CreatePortalRequest(BaseModel):
    return_url: str


async def get_or_create_stripe_customer(user: User, db: AsyncSession) -> Subscription:
    """获取或创建 Stripe 客户"""
    # 查找现有订阅
    from sqlalchemy import select
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user.id)
    )
    subscription = result.scalar_one_or_none()
    
    if subscription and subscription.stripe_customer_id:
        return subscription
    
    # 创建 Stripe 客户
    if settings.STRIPE_SECRET_KEY:
        customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": str(user.id)}
        )
    else:
        # Mock 模式
        customer = type("MockCustomer", (), {"id": f"cus_mock_{user.id}"})()
    
    # 创建或更新订阅记录
    if not subscription:
        subscription = Subscription(
            user_id=user.id,
            stripe_customer_id=customer.id,
            plan=PlanType.FREE.value,
            status="active"
        )
        db.add(subscription)
    else:
        subscription.stripe_customer_id = customer.id
    
    await db.commit()
    await db.refresh(subscription)
    return subscription


async def update_subscription(
    user_id: str,
    subscription_id: str,
    customer_id: str,
    price_id: str,
    db: AsyncSession
) -> Subscription:
    """更新用户订阅状态"""
    from sqlalchemy import select
    result = await db.execute(
        select(Subscription).join(User).where(User.external_id == user_id)
    )
    subscription = result.scalar_one_or_none()
    
    if not subscription:
        # 查找用户
        user_result = await db.execute(
            select(User).where(User.external_id == user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        subscription = Subscription(
            user_id=user.id,
            stripe_customer_id=customer_id,
            stripe_subscription_id=subscription_id,
            stripe_price_id=price_id
        )
        db.add(subscription)
    else:
        subscription.stripe_subscription_id = subscription_id
        subscription.stripe_customer_id = customer_id
        subscription.stripe_price_id = price_id
    
    # 根据 price_id 确定计划类型
    if price_id == settings.STRIPE_PRICE_PRO:
        subscription.plan = PlanType.PRO.value
    elif price_id == settings.STRIPE_PRICE_TEAM:
        subscription.plan = PlanType.TEAM.value
    else:
        subscription.plan = PlanType.FREE.value
    
    subscription.status = "active"
    await db.commit()
    await db.refresh(subscription)
    return subscription


@router.get("/plans")
async def get_plans():
    """获取定价计划"""
    plans_list = [
        {"id": key, **value}
        for key, value in PLANS.items()
    ]
    return {
        "plans": plans_list,
        "current_plan": None  # 前端会根据用户状态显示
    }


@router.get("/plans/{plan_id}")
async def get_plan_details(plan_id: str):
    """获取单个计划详情"""
    if plan_id not in PLANS:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"id": plan_id, **PLANS[plan_id]}


@router.post("/checkout")
async def create_checkout_session(
    data: CreateCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建 Stripe Checkout Session"""
    from sqlalchemy import select
    
    # 获取用户
    result = await db.execute(
        select(User).where(User.external_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not settings.STRIPE_SECRET_KEY:
        # 测试模式：返回模拟 session
        return {
            "url": data.success_url + "?test=1",
            "session_id": "cs_test_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        }
    
    # 获取或创建 Stripe 客户
    subscription = await get_or_create_stripe_customer(user, db)
    
    try:
        session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            mode="subscription",
            line_items=[{
                "price": data.price_id,
                "quantity": 1
            }],
            success_url=data.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=data.cancel_url,
            metadata={
                "user_id": user_id
            }
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/portal")
async def create_portal_session(
    data: CreatePortalRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """创建客户门户 Session（管理订阅）"""
    from sqlalchemy import select
    
    # 获取用户
    result = await db.execute(
        select(User).where(User.external_id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not settings.STRIPE_SECRET_KEY:
        return {"url": data.return_url}
    
    subscription = await get_or_create_stripe_customer(user, db)
    
    try:
        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=data.return_url
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
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
        price_id = data.get("line_items", {}).get("data", [{}])[0].get("price", {}).get("id")
        
        if user_id and subscription_id:
            try:
                await update_subscription(user_id, subscription_id, customer_id, price_id, db)
            except Exception as e:
                # 记录错误但不返回 500（Stripe 会重试）
                print(f"Error updating subscription: {e}")
        
    elif event_type == "customer.subscription.updated":
        # 订阅更新
        subscription_id = data.get("id")
        status = data.get("status")
        price_id = data.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
        
        from sqlalchemy import select
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = status
            if price_id == settings.STRIPE_PRICE_PRO:
                sub.plan = PlanType.PRO.value
            elif price_id == settings.STRIPE_PRICE_TEAM:
                sub.plan = PlanType.TEAM.value
            await db.commit()
        
    elif event_type == "customer.subscription.deleted":
        # 订阅取消
        subscription_id = data.get("id")
        
        from sqlalchemy import select
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = "canceled"
            sub.plan = PlanType.FREE.value
            sub.cancel_at_period_end = False
            await db.commit()
    
    return {"received": True}


@router.get("/subscription")
async def get_subscription(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """获取当前订阅状态"""
    from sqlalchemy import select
    
    # 获取用户订阅。走 ensure_subscription 而不是「没有就返回一份假数据」：
    # 历史用户没有订阅记录，返回全 0 会让前端把超额用户显示成「刚注册」。
    subscription = await ensure_subscription(db, user_id)

    # 上限必须取自与实际判定同一处。此前这里自己用 is_pro 二分，
    # 与 entitlement 里的逻辑各写一份，团队版会看到专业版的上限。
    limits = limits_for(subscription)

    return {
        "plan": subscription.plan,
        "status": subscription.status,
        "agents_used": subscription.agents_used or 0,
        "messages_used": subscription.messages_used or 0,
        "agents_limit": limits[Resource.AGENTS],
        "messages_limit": limits[Resource.MESSAGES],
        "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None
    }
