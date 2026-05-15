import uuid

from confluent_kafka import Producer
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import CurrentUser, get_current_user, get_db
from app.models.domain import OrderStatus
from app.models.schemas import (
    OrderCreate,
    OrderItemResponse,
    OrderResponse,
    StatusUpdate,
)
from app.repositories.order_repository import OrderRepository
from app.services.order_service import OrderService
from app.services.routing_client import RoutingClient

router = APIRouter()


def _order_to_response(order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        customer_id=order.customer_id,
        restaurant_id=order.restaurant_id,
        courier_id=order.courier_id,
        status=order.status,
        total_price=order.total_price,
        items=[
            OrderItemResponse(
                id=oi.id,
                menu_item_id=oi.menu_item_id,
                name=oi.name,
                quantity=oi.quantity,
                unit_price=oi.unit_price,
            )
            for oi in order.items
        ],
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def get_kafka_producer() -> Producer:
    return Producer({"bootstrap.servers": settings.kafka_brokers})


def get_routing_client() -> RoutingClient:
    return RoutingClient(base_url=settings.routing_service_url)


def get_order_service(
    db: AsyncSession = Depends(get_db),
    kafka_producer: Producer = Depends(get_kafka_producer),
    routing_client: RoutingClient = Depends(get_routing_client),
) -> OrderService:
    return OrderService(
        order_repo=OrderRepository(db),
        kafka_producer=kafka_producer,
        routing_client=routing_client,
    )


@router.post(
    "/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED
)
async def create_order(
    payload: OrderCreate,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Create a new order. Only customers can place orders."""
    if current_user.role != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can place orders",
        )
    order = await service.create_order(
        customer_id=current_user.user_id, payload=payload
    )
    return _order_to_response(order)


@router.get("/orders", response_model=list[OrderResponse])
async def list_orders(
    customer_id: uuid.UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """List orders. Customers see their own; restaurants can query by customer_id."""
    if current_user.role == "customer":
        target_id = current_user.user_id
    elif current_user.role == "restaurant":
        if customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="customer_id query parameter is required for restaurant role",
            )
        target_id = customer_id
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    orders = await service.list_orders(customer_id=target_id)
    return [_order_to_response(o) for o in orders]


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Get a single order by ID. Owner customer, assigned courier, or restaurant only."""
    order = await service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Access control: customer (owner), courier (assigned), or restaurant (owner)
    if current_user.role == "customer" and order.customer_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if current_user.role == "courier" and (
        order.courier_id is None or order.courier_id != current_user.user_id
    ):
        raise HTTPException(status_code=403, detail="Access denied")
    if (
        current_user.role == "restaurant"
        and order.restaurant_id != current_user.user_id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    return _order_to_response(order)


@router.patch("/orders/{order_id}/status", response_model=OrderResponse)
async def update_status(
    order_id: uuid.UUID,
    payload: StatusUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Update order status. Role-based transitions per api-contracts.md."""
    if current_user.role not in ("restaurant", "courier", "customer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Fetch order first for ownership checks
    order = await service.get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    new_status = payload.status

    # CANCELLED: allowed for restaurant (owner) or customer (owner)
    if new_status == OrderStatus.CANCELLED:
        if current_user.role == "restaurant":
            if order.restaurant_id != current_user.user_id:
                raise HTTPException(status_code=403, detail="Forbidden")
        elif current_user.role == "customer":
            if order.customer_id != current_user.user_id:
                raise HTTPException(status_code=403, detail="Forbidden")
        else:
            raise HTTPException(status_code=403, detail="Forbidden")
    # PLACED → PREPARING: restaurant (owner) only
    elif order.status == OrderStatus.PLACED and new_status == OrderStatus.PREPARING:
        if current_user.role != "restaurant":
            raise HTTPException(status_code=403, detail="Forbidden")
        if order.restaurant_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    # PREPARING → READY: restaurant (owner) only
    elif order.status == OrderStatus.PREPARING and new_status == OrderStatus.READY:
        if current_user.role != "restaurant":
            raise HTTPException(status_code=403, detail="Forbidden")
        if order.restaurant_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    # READY → PICKED_UP: courier (assigned) only
    elif order.status == OrderStatus.READY and new_status == OrderStatus.PICKED_UP:
        if current_user.role != "courier":
            raise HTTPException(status_code=403, detail="Forbidden")
        if order.courier_id is None or order.courier_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    # PICKED_UP → DELIVERED: courier (assigned) only
    elif order.status == OrderStatus.PICKED_UP and new_status == OrderStatus.DELIVERED:
        if current_user.role != "courier":
            raise HTTPException(status_code=403, detail="Forbidden")
        if order.courier_id is None or order.courier_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
    else:
        # Generic invalid transition
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid status transition: {order.status.value} → {new_status.value}",
        )

    try:
        updated = await service.update_status(order_id, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return _order_to_response(updated)
