from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Order as OrderORM
from app.db.models import OrderItem as OrderItemORM
from app.db.models import OrderStatus
from app.models.domain import Order, OrderItem


class OrderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        customer_id,
        restaurant_id,
        items: list[dict],
        total_price: float,
    ) -> Order:
        row = OrderORM(
            customer_id=customer_id,
            restaurant_id=restaurant_id,
            status=OrderStatus.PLACED,
            total_price=total_price,
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)

        item_rows = []
        for item in items:
            oi = OrderItemORM(
                order_id=row.id,
                menu_item_id=item["menu_item_id"],
                name=item["name"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
            )
            self.db.add(oi)
            item_rows.append(oi)

        await self.db.flush()
        for oi in item_rows:
            await self.db.refresh(oi)

        return self._to_domain(row, item_rows)

    async def find_by_id(self, order_id) -> Order | None:
        stmt = (
            select(OrderORM)
            .options(selectinload(OrderORM.items))
            .where(OrderORM.id == order_id)
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_domain(row)

    async def find_by_customer(self, customer_id) -> list[Order]:
        stmt = (
            select(OrderORM)
            .options(selectinload(OrderORM.items))
            .where(OrderORM.customer_id == customer_id)
            .order_by(OrderORM.created_at.desc())
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [self._row_to_domain(r) for r in rows]

    async def update_courier(self, order_id, courier_id) -> None:
        stmt = select(OrderORM).where(OrderORM.id == order_id)
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is not None:
            row.courier_id = courier_id
            await self.db.flush()

    async def update_status(self, order_id, new_status: OrderStatus) -> Order | None:
        stmt = (
            select(OrderORM)
            .options(selectinload(OrderORM.items))
            .where(OrderORM.id == order_id)
        )
        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.status = new_status
        await self.db.flush()
        await self.db.refresh(row)
        return self._row_to_domain(row)

    # --- Helpers ---

    def _item_to_domain(self, oi: OrderItemORM) -> OrderItem:
        return OrderItem(
            id=oi.id,
            menu_item_id=oi.menu_item_id,
            name=oi.name,
            quantity=oi.quantity,
            unit_price=oi.unit_price,
        )

    def _row_to_domain(self, row: OrderORM) -> Order:
        return Order(
            id=row.id,
            customer_id=row.customer_id,
            restaurant_id=row.restaurant_id,
            status=row.status,
            total_price=row.total_price,
            items=[self._item_to_domain(oi) for oi in row.items],
            courier_id=row.courier_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _to_domain(self, row: OrderORM, item_rows: list[OrderItemORM]) -> Order:
        return Order(
            id=row.id,
            customer_id=row.customer_id,
            restaurant_id=row.restaurant_id,
            status=row.status,
            total_price=row.total_price,
            items=[self._item_to_domain(oi) for oi in item_rows],
            courier_id=row.courier_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
