from datetime import datetime

from sqlalchemy import Float, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    paid_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    split_type: Mapped[str] = mapped_column(String(20), nullable=False, default="equal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    splits: Mapped[list["ExpenseSplit"]] = relationship(
        back_populates="expense", cascade="all, delete-orphan"
    )


class ExpenseSplit(Base):
    __tablename__ = "expense_splits"

    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    expense: Mapped["Expense"] = relationship(back_populates="splits")
