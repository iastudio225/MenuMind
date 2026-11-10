"""Async PostgreSQL document adapter used by the existing FastAPI services.

Supabase is the managed PostgreSQL host; the application connects with its
PostgreSQL connection string. JSONB preserves the current backend data shape,
while each collection is isolated in a PostgreSQL table.
"""
import json
import os
import re
import secrets
import logging
import time
from datetime import date, datetime

import asyncpg

logger = logging.getLogger(__name__)


async def _fetch_timed(label, fetch, sql, *args):
    started = time.perf_counter()
    try:
        return await fetch(sql, *args)
    except Exception:
        # SQL contains placeholders only; never log bound values or row data.
        logger.exception("PostgreSQL query failed label=%s sql=%s", label, " ".join(sql.split()))
        raise
    finally:
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms >= 100:
            logger.warning("Slow PostgreSQL query label=%s duration_ms=%.1f", label, elapsed_ms)


COLLECTIONS = (
    "users", "restaurants", "plans", "menu_items", "menu_categories",
    "menu_option_groups", "menu_options", "weekly_menus", "orders", "carts",
    "customers", "order_status_history", "ai_conversations", "delivery_zones",
    "audit_logs", "password_reset_tokens", "login_attempts",
    "password_reset_requests", "counters", "pending_registrations",
    "email_verification_tokens", "trial_eligibility", "license_operations",
    "license_history", "verification_rate_limits", "license_conversion_requests",
)


def _plain(value):
    if hasattr(value, "binary") and value.__class__.__name__ == "ObjectId":
        return str(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _path_expr(path: str) -> str:
    parts = path.split(".")
    return "data #>> '{" + ",".join(p.replace("'", "") for p in parts) + "}'"


class Result:
    def __init__(self, count=0, inserted_id=None):
        self.deleted_count = count
        self.modified_count = count
        self.matched_count = count
        self.inserted_id = inserted_id


class Cursor:
    def __init__(self, collection, query):
        self.collection, self.query = collection, query
        self.sort_spec, self.limit_n = [], None
        self.skip_n = 0

    def sort(self, key, direction=1):
        self.sort_spec = [(key, direction)] if isinstance(key, str) else list(key)
        return self

    def limit(self, value):
        self.limit_n = value
        return self

    def skip(self, value):
        self.skip_n = max(0, int(value))
        return self

    async def to_list(self, length=None):
        return await self.collection._select(self.query, self.sort_spec, self.limit_n or length, self.skip_n)


class Collection:
    def __init__(self, database, name):
        if name not in COLLECTIONS:
            raise ValueError(f"Unknown PostgreSQL collection: {name}")
        self.database, self.name = database, name
        self.table = f'"{name}"'

    def _where(self, query):
        terms, args = [], []
        def add(path, value):
            if path == "_id":
                path = "id"
                if isinstance(value, dict):
                    raise ValueError("Operator filters on _id are unsupported")
                args.append(str(value)); terms.append(f"id = ${len(args)}")
                return
            if not isinstance(value, dict):
                args.append(json.dumps(_plain(value)))
                exact_arg = len(args)
                args.append(json.dumps([_plain(value)]))
                terms.append(f"(data #> '{{{path}}}' = ${exact_arg}::jsonb OR data #> '{{{path}}}' @> ${len(args)}::jsonb)")
                return
            for op, operand in value.items():
                expr = _path_expr(path)
                if op == "$exists":
                    terms.append(f"(data #> '{{{path}}}' IS {'NOT ' if operand else ''}NULL")
                elif op in ("$ne", "$gt", "$gte", "$lt", "$lte"):
                    sqlop = {"$ne":"IS DISTINCT FROM", "$gt":">", "$gte":">=", "$lt":"<", "$lte":"<="}[op]
                    args.append(str(operand)); terms.append(f"{expr} {sqlop} ${len(args)}")
                elif op == "$in":
                    args.append([str(x) for x in operand]); terms.append(f"{expr} = ANY(${len(args)}::text[])")
                elif op == "$contains":
                    args.append(json.dumps(_plain(operand))); terms.append(f"data #> '{{{path}}}' @> ${len(args)}::jsonb")
                elif op == "$regex":
                    args.append(str(operand)); terms.append(f"{expr} ~* ${len(args)}")
                elif op == "$options":
                    continue
                else:
                    raise ValueError(f"Unsupported PostgreSQL query operator: {op}")
        for key, value in query.items():
            if key == "$or":
                parts = []
                for subquery in value:
                    subwhere, subargs = self._where(subquery)
                    offset = len(args)
                    for item in subargs:
                        args.append(item)
                    parts.append(re.sub(r"\$(\d+)", lambda m: f"${int(m.group(1))+offset}", subwhere))
                terms.append("(" + " OR ".join(parts) + ")")
            else:
                add(key, value)
        return (" AND ".join(terms) or "TRUE"), args

    async def _select(self, query, sort_spec=(), limit=None, offset=0):
        where, args = self._where(query or {})
        order = ""
        if sort_spec:
            order = " ORDER BY " + ", ".join(
                ("id" if k == "_id" else _path_expr(k)) + (" DESC" if d < 0 else " ASC")
                for k, d in sort_spec
            )
        limit_sql = ""
        if limit is not None:
            args.append(int(limit)); limit_sql = f" LIMIT ${len(args)}"
        if offset:
            args.append(int(offset)); limit_sql += f" OFFSET ${len(args)}"
        sql = f"SELECT id, data FROM {self.table} WHERE {where}{order}{limit_sql}"
        records = await _fetch_timed(f"{self.name}.select", self.database.pool.fetch, sql, *args)
        return [{"_id": r["id"], **json.loads(r["data"])} for r in records]

    async def find_one(self, query, projection=None):
        rows = await self._select(query, limit=1)
        return rows[0] if rows else None

    def find(self, query=None, projection=None):
        return Cursor(self, query or {})

    async def find_by_ids(self, ids, query=None):
        ids = [str(ident) for ident in ids]
        if not ids:
            return []
        where, args = self._where(query or {})
        args.append(ids)
        sql = f"SELECT id, data FROM {self.table} WHERE id = ANY(${len(args)}::text[]) AND ({where})"
        records = await _fetch_timed(f"{self.name}.find_by_ids", self.database.pool.fetch, sql, *args)
        return [{"_id": r["id"], **json.loads(r["data"])} for r in records]

    async def insert_one(self, document):
        doc = _plain(dict(document)); ident = str(doc.pop("_id", None) or secrets.token_hex(12))
        await self.database.pool.execute(f"INSERT INTO {self.table}(id,data) VALUES($1,$2::jsonb)", ident, json.dumps(doc))
        return Result(inserted_id=ident)

    def _update(self, old, update):
        doc = dict(old)
        if isinstance(update, list):
            for stage in update:
                for op, fields in stage.items():
                    if op != "$set": raise ValueError(f"Unsupported PostgreSQL update pipeline stage: {op}")
                    for key, value in fields.items():
                        if isinstance(value, dict) and "$ifNull" in value:
                            source = value["$ifNull"][0]
                            doc[key] = doc.get(source[1:], value["$ifNull"][1]) if isinstance(source, str) and source.startswith("$") else value["$ifNull"][1]
                        else: doc[key] = value
            return doc
        for op, fields in update.items():
            if op == "$set":
                doc.update(_plain(fields))
            elif op == "$setOnInsert":
                continue
            elif op == "$inc":
                for key, value in fields.items(): doc[key] = doc.get(key, 0) + value
            elif op in ("$push", "$addToSet"):
                for key, value in fields.items():
                    arr = list(doc.get(key, [])); value = _plain(value)
                    if op == "$push" or value not in arr: arr.append(value)
                    doc[key] = arr
            elif op == "$pull":
                for key, value in fields.items(): doc[key] = [x for x in doc.get(key, []) if x != value]
            else:
                raise ValueError(f"Unsupported PostgreSQL update operator: {op}")
        return doc

    async def update_one(self, query, update, upsert=False):
        return await self._update_matching(query, update, upsert, False)

    async def update_many(self, query, update):
        return await self._update_matching(query, update, False, True)

    async def _update_matching(self, query, update, upsert, many):
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                where, args = self._where(query or {})
                sql = f"SELECT id,data FROM {self.table} WHERE {where}" + ("" if many else " LIMIT 1") + " FOR UPDATE"
                records = await _fetch_timed(f"{self.name}.update_lock", conn.fetch, sql, *args)
                if not records and upsert:
                    base = {k:v for k,v in (query or {}).items() if not isinstance(v, dict)}
                    if "_id" in base: base.pop("_id")
                    base.update({k:v for k,v in update.get("$setOnInsert", {}).items()})
                    doc = self._update(base, update); ident = str(doc.pop("_id", query.get("_id") or secrets.token_hex(12)))
                    await conn.execute(f"INSERT INTO {self.table}(id,data) VALUES($1,$2::jsonb)", ident, json.dumps(doc))
                    return Result(1, ident)
                for row in records:
                    doc = self._update(json.loads(row["data"]), update)
                    await conn.execute(f"UPDATE {self.table} SET data=$2::jsonb WHERE id=$1", row["id"], json.dumps(doc))
                return Result(len(records))

    async def find_one_and_update(self, query, update, upsert=False, return_document=None):
        where, args = self._where(query or {})
        async with self.database.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(f"SELECT id,data FROM {self.table} WHERE {where} LIMIT 1 FOR UPDATE", *args)
                if row:
                    before = {"_id": row["id"], **json.loads(row["data"])}
                    after_data = self._update(json.loads(row["data"]), update)
                    await conn.execute(f"UPDATE {self.table} SET data=$2::jsonb WHERE id=$1", row["id"], json.dumps(after_data))
                    after = {"_id": row["id"], **after_data}
                    # pymongo ReturnDocument.AFTER has numeric value True.
                    return before if return_document is False else after
                if not upsert:
                    return None
                base = {k:v for k,v in (query or {}).items() if not isinstance(v, dict) and k != "_id"}
                ident = str((query or {}).get("_id") or secrets.token_hex(12))
                if "$inc" in update and len(update) == 1:
                    fields = update["$inc"]
                    existing = await conn.fetchrow(f"SELECT data FROM {self.table} WHERE id=$1 FOR UPDATE", ident)
                    if existing:
                        doc = self._update(json.loads(existing["data"]), update)
                        await conn.execute(f"UPDATE {self.table} SET data=$2::jsonb WHERE id=$1", ident, json.dumps(doc))
                    else:
                        doc = {**base, **fields}
                        inserted = await conn.execute(f"INSERT INTO {self.table}(id,data) VALUES($1,$2::jsonb) ON CONFLICT(id) DO NOTHING", ident, json.dumps(doc))
                        if inserted.endswith("0"):
                            current = await conn.fetchrow(f"SELECT data FROM {self.table} WHERE id=$1 FOR UPDATE", ident)
                            doc = self._update(json.loads(current["data"]), update)
                            await conn.execute(f"UPDATE {self.table} SET data=$2::jsonb WHERE id=$1", ident, json.dumps(doc))
                else:
                    doc = self._update(base, update)
                    await conn.execute(f"INSERT INTO {self.table}(id,data) VALUES($1,$2::jsonb)", ident, json.dumps(doc))
                return {"_id": ident, **doc}

    async def delete_one(self, query):
        return await self._delete(query, False)

    async def delete_many(self, query):
        return await self._delete(query, True)

    async def _delete(self, query, many):
        where, args = self._where(query or {})
        ids = await self.database.pool.fetch(f"SELECT id FROM {self.table} WHERE {where}" + ("" if many else " LIMIT 1"), *args)
        if not ids: return Result()
        result = await self.database.pool.execute(f"DELETE FROM {self.table} WHERE id = ANY($1::text[])", [r["id"] for r in ids])
        return Result(int(result.rsplit(" ", 1)[-1]))

    async def count_documents(self, query, limit=0):
        where, args = self._where(query or {})
        suffix = f" LIMIT {int(limit)}" if limit else ""
        return await self.database.pool.fetchval(f"SELECT count(*) FROM (SELECT 1 FROM {self.table} WHERE {where}{suffix}) q", *args)

    async def create_index(self, *args, **kwargs):
        # Indexes are versioned in backend/migrations and applied explicitly.
        return None


class Database:
    def __init__(self):
        self.pool = None
        for name in COLLECTIONS:
            setattr(self, name, Collection(self, name))

    async def connect(self):
        dsn = os.environ.get("SUPABASE_DB_URL")
        if not dsn:
            raise RuntimeError("SUPABASE_DB_URL is required (Supabase PostgreSQL connection string)")
        self.pool = await asyncpg.create_pool(dsn, min_size=1, max_size=10, command_timeout=30)

    async def dashboard_overview(self, restaurant_id: str, today: str, week_start: str) -> dict:
        """Aggregate dashboard metrics in Postgres without transferring order rows."""
        row = await self.pool.fetchrow(
            """
            WITH scoped_orders AS (
                SELECT data->>'created_at' AS created_at,
                       data->>'status' AS status,
                       CASE WHEN data->>'total' ~ '^-?[0-9]+(\\.[0-9]+)?$'
                            THEN (data->>'total')::numeric ELSE 0 END AS total
                FROM public.orders
                WHERE data->>'restaurant_id' = $1
            ), order_stats AS (
                SELECT
                    count(*) FILTER (WHERE created_at LIKE $2 || '%') AS orders_today,
                    count(*) FILTER (WHERE created_at >= $3) AS orders_week,
                    coalesce(sum(total) FILTER (WHERE created_at LIKE $2 || '%' AND status IS DISTINCT FROM 'CANCELLED'), 0)::bigint AS revenue_today,
                    coalesce(sum(total) FILTER (WHERE created_at >= $3 AND status IS DISTINCT FROM 'CANCELLED'), 0)::bigint AS revenue_week,
                    count(*) FILTER (WHERE status = 'PENDING') AS pending,
                    count(*) FILTER (WHERE status = 'PREPARING') AS preparing,
                    count(*) FILTER (WHERE status = 'READY') AS ready,
                    count(*) FILTER (WHERE created_at LIKE $2 || '%' AND status = 'DELIVERED') AS completed_today,
                    count(*) FILTER (WHERE status IS DISTINCT FROM 'CANCELLED') AS non_cancelled,
                    coalesce(sum(total) FILTER (WHERE status IS DISTINCT FROM 'CANCELLED'), 0) AS revenue_total,
                    count(*) AS total_orders
                FROM scoped_orders
            )
            SELECT order_stats.*,
                   CASE WHEN non_cancelled = 0 THEN 0
                        ELSE round(revenue_total / non_cancelled)::bigint END AS avg_basket,
                   (SELECT count(*) FROM public.menu_items WHERE data->>'restaurant_id' = $1) AS menu_items,
                   (SELECT count(*) FROM public.customers WHERE data->>'restaurant_id' = $1) AS customers,
                   (SELECT count(*) FROM public.users WHERE data->>'restaurant_id' = $1) AS users
            FROM order_stats
            """,
            restaurant_id, today, week_start,
        )
        return dict(row)

    async def admin_restaurants_with_stats(self):
        """Fetch the admin restaurant list with owner and order counts in one query."""
        rows = await self.pool.fetch(
            """
            SELECT r.id, r.data,
                   (SELECT u.data->>'email' FROM public.users u
                    WHERE u.data->>'restaurant_id' = r.id
                      AND u.data->>'role' = $1 LIMIT 1) AS owner_email,
                   (SELECT count(*) FROM public.orders o
                    WHERE o.data->>'restaurant_id' = r.id) AS orders_count
            FROM public.restaurants r
            WHERE r.data->>'status' IS DISTINCT FROM 'deleted'
            ORDER BY r.data->>'created_at' DESC
            LIMIT 1000
            """, "RESTAURANT_OWNER",
        )
        return [{"_id": row["id"], **json.loads(row["data"]),
                 "owner_email": row["owner_email"], "orders_count": row["orders_count"]}
                for row in rows]

    async def weekly_menu_data(self, restaurant_id: str):
        """Read weekly plans and the tenant catalogue in one PostgreSQL round trip."""
        rows = await _fetch_timed(
            "weekly_menu_data", self.pool.fetch,
            """
            SELECT 'weekly' AS kind, id, data FROM public.weekly_menus
            WHERE data->>'restaurant_id' = $1
            UNION ALL
            SELECT 'item' AS kind, id, data FROM public.menu_items
            WHERE data->>'restaurant_id' = $1
            """, restaurant_id,
        )
        plans, items = [], []
        for row in rows:
            value = {"_id": row["id"], **json.loads(row["data"])}
            (plans if row["kind"] == "weekly" else items).append(value)
        return plans, items

    async def customers_page(self, restaurant_id: str, search: str, page: int, page_size: int):
        offset = (page - 1) * page_size
        rows = await self.pool.fetch(
            """
            WITH scoped_customers AS (
              SELECT c.id, c.data
              FROM public.customers c
              WHERE c.data->>'restaurant_id' = $1
                AND ($2 = '' OR concat_ws(' ', c.data->>'first_name', c.data->>'last_name', c.data->>'phone') ILIKE '%' || $2 || '%')
            ), stats AS (
              SELECT sc.id, sc.data,
                     count(o.id) AS orders_count,
                     coalesce(sum(CASE WHEN o.data->>'status' IS DISTINCT FROM 'CANCELLED'
                       AND coalesce(o.data->>'total','') ~ '^-?[0-9]+(\\.[0-9]+)?$'
                       THEN (o.data->>'total')::numeric ELSE 0 END), 0)::bigint AS total_spent,
                     max(o.data->>'created_at') AS last_order_at
              FROM scoped_customers sc
              LEFT JOIN public.orders o ON o.data->>'customer_id' = sc.id AND o.data->>'restaurant_id' = $1
              GROUP BY sc.id, sc.data
            )
            SELECT *, count(*) OVER() AS total_count FROM stats
            ORDER BY last_order_at DESC NULLS LAST, id
            LIMIT $3 OFFSET $4
            """, restaurant_id, search.strip(), page_size, offset,
        )
        return [{"_id": row["id"], **json.loads(row["data"]),
                 "orders_count": row["orders_count"], "total_spent": row["total_spent"],
                 "last_order_at": row["last_order_at"], "total_count": row["total_count"]}
                for row in rows]

    async def close(self):
        if self.pool:
            await self.pool.close(); self.pool = None


db = Database()


def get_client():
    return db
