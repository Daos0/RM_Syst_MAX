from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaxAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16384)


class TelegramAuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16384)


class BootstrapRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    username: str | None = Field(default=None, max_length=64)
    locale: str = Field(default="ru", min_length=2, max_length=12)


class ListCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(pattern="^(personal|family|shared)$")
    template_code: str | None = Field(default=None, max_length=80)


class ListUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ListItemsStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|purchased)$")


class ItemCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    unit: str | None = Field(default=None, max_length=16)
    department_id: int | None = Field(default=None, ge=1)
    note: str | None = Field(default=None, max_length=1000)


class ItemUpdateRequest(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)
    unit: str | None = Field(default=None, min_length=1, max_length=16)
    department_id: int | None = Field(default=None, ge=1)
    note: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(active|purchased|unavailable)$")
    mark: str | None = Field(default=None, pattern="^(|blue|amber|violet|coral)$")


class RecipeAddRequest(BaseModel):
    variant_id: UUID | None = None
    yield_quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    excluded_product_ids: list[UUID] = Field(default_factory=list, max_length=100)


class LocalItemMigration(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(min_length=1, max_length=16)
    category: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)
    status: str = Field(default="active", pattern="^(active|purchased|unavailable)$")
    mark: str = Field(default="", pattern="^(|blue|amber|violet|coral)$")


class LocalListMigration(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    category: str = Field(pattern="^(personal|family|shared)$")
    items: list[LocalItemMigration] = Field(default_factory=list, max_length=500)


class LocalCatalogMigration(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    unit: str = Field(min_length=1, max_length=16)
    category: str | None = Field(default=None, max_length=120)


class LocalMigrationRequest(BaseModel):
    migration_id: str = Field(pattern="^[a-z0-9_-]{1,64}$")
    lists: list[LocalListMigration] = Field(default_factory=list, max_length=50)
    personal_catalog: list[LocalCatalogMigration] = Field(default_factory=list, max_length=500)
    product_usage: dict[str, dict] = Field(default_factory=dict)
    recipe_usage: dict[str, dict] = Field(default_factory=dict)


class ItemView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    quantity: Decimal
    unit: str
    department_id: int
    note: str | None
    mark: str
    status: str
    assigned_member_id: UUID | None
    purchased_by_member_id: UUID | None
    version: int
