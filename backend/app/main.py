from datetime import datetime, timezone
import json
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, status, Query
import bcrypt
import psycopg2
from psycopg2 import sql
import socket
import requests
import ssl
from requests.adapters import HTTPAdapter
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from neo4j import GraphDatabase

from .auth import callback, create_session_from_id_token, login, require_user
from .config import settings
from .db import get_db, init_db
from .schemas import (
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    InternalUserOut,
    InternalUserCreate,
    InternalUserPasswordUpdate,
    InstanceCreate,
    InstanceOut,
    InstanceUpdate,
    OnboardRequest,
    OnboardResponse,
    SessionOut,
    PostgresTestRequest,
    Neo4jTestRequest,
    TokenExchangeRequest,
)

app = FastAPI(title=settings.app_name)
LAST_BFF_ERROR: dict | None = None


class TLSAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        pool_kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(connections, maxsize, block, **pool_kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def _build_tls_context() -> ssl.SSLContext | None:
    version = (settings.bff_tls_version or "").strip().lower()
    if version in {"1.3", "tls1.3", "tlsv1.3"} and hasattr(ssl, "TLSVersion"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        return context
    if version in {"1.2", "tls1.2", "tlsv1.2"} and hasattr(ssl, "TLSVersion"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_2
        return context
    if version in {"1.2+", "1.2-1.3", "tls1.2-1.3"} and hasattr(ssl, "TLSVersion"):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.maximum_version = ssl.TLSVersion.TLSv1_3
        return context
    return None

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=False,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@app.get("/api/bff-error")
def get_bff_error(user: dict = Depends(require_user)) -> dict:
    if not LAST_BFF_ERROR:
        return {"detail": None, "at": None}
    return LAST_BFF_ERROR


def _row_to_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}


def _compose_name(first: str | None, last: str | None) -> str | None:
    parts = [part.strip() for part in (first, last) if part and part.strip()]
    return " ".join(parts) if parts else None


def _push_customer_to_neo4j(
    instance: dict, customer: dict, tenant_id: str, subscriber: str | None, tenant_name: str
) -> None:
    host = instance.get("neo4j_host")
    user = instance.get("neo4j_user")
    password = instance.get("neo4j_password")
    port = instance.get("neo4j_port") or 7687
    if not host or not user or not password:
        raise HTTPException(status_code=400, detail="Neo4j credentials are missing.")
    department = (customer.get("department") or "Cybersecurity").strip()
    first_name = (customer.get("first_name") or "").strip()
    last_name = (customer.get("last_name") or "").strip()
    email = (customer.get("contact_email") or "").strip()
    display_name = (
        _compose_name(first_name, last_name)
        or customer.get("name")
        or (tenant_name or tenant_id)
    )
    user_id = email or (display_name.replace(" ", ".").lower() if display_name else "")
    if not user_id:
        raise HTTPException(status_code=400, detail="User id could not be derived.")
    cypher = """
    MERGE (t:TENANT {id: $tenant_id, subscriber: $subscriber, tenant: $tenant_name})
    ON CREATE SET t.creationTime = $now, t.internalId = randomUUID(), t.new = true, t.timestamp = timestamp()
    ON MATCH SET t.new = false, t.timestamp = timestamp()
    MERGE (i:INSTANCE {id: $instance_id, subscriber: $subscriber, tenant: $tenant_name})
    ON CREATE SET i.creationTime = $now, i.internalId = randomUUID(), i.new = true, i.timestamp = timestamp()
    ON MATCH SET i.new = false, i.timestamp = timestamp()
    MERGE (u:USER {id: $user_id, subscriber: $subscriber, tenant: $tenant_name})
    ON CREATE SET u.displayName = $display_name, u.givenName = $first_name, u.surname = $last_name,
                  u.mail = $email, u.userPrincipalName = $email, u.internalId = randomUUID(),
                  u.new = true, u.timestamp = timestamp()
    ON MATCH SET u.displayName = $display_name, u.givenName = $first_name, u.surname = $last_name,
                 u.mail = $email, u.userPrincipalName = $email, u.new = false, u.timestamp = timestamp()
    MERGE (e:EMAIL {id: $email, subscriber: $subscriber, tenant: $tenant_name})
    ON CREATE SET e.internalId = randomUUID(), e.new = true, e.timestamp = timestamp()
    ON MATCH SET e.new = false, e.timestamp = timestamp()
    MERGE (d:DEPARTMENT {id: $department, subscriber: $subscriber, tenant: $tenant_name})
    ON CREATE SET d.name = $department, d.internalId = randomUUID(), d.new = true, d.timestamp = timestamp()
    ON MATCH SET d.name = $department, d.new = false, d.timestamp = timestamp()
    MERGE (t)-[:HAS_INSTANCE]->(i)
    MERGE (i)-[:HAS_USER]->(u)
    MERGE (u)-[:HAS_EMAIL]->(e)
    MERGE (u)-[:HAS_DEPARTMENT]->(d)
    """
    params = {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "subscriber": subscriber or "",
        "instance_id": instance.get("id") or customer.get("instance_id"),
        "user_id": user_id,
        "display_name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "department": department,
        "now": utc_now(),
    }
    driver = GraphDatabase.driver(f"bolt://{host}:{port}", auth=(user, password))
    try:
        with driver.session() as session:
            session.run(cypher, params)
    finally:
        driver.close()


def _build_customer_name(payload: CustomerCreate) -> str | None:
    if payload.name:
        return payload.name.strip()
    return _compose_name(payload.first_name, payload.last_name)


def _build_bff_payload(payload: CustomerCreate) -> dict:
    first = (payload.first_name or "").strip()
    last = (payload.last_name or "").strip()
    if (not first or not last) and payload.name:
        parts = [part.strip() for part in payload.name.split() if part.strip()]
        if not first and parts:
            first = parts[0]
        if not last and len(parts) > 1:
            last = " ".join(parts[1:])
    email = (payload.contact_email or "").strip()
    vendor = (payload.vendor or "").strip()
    if not first or not last or not email or not vendor:
        raise HTTPException(
            status_code=400,
            detail="Customer first name, last name, email, and vendor are required for onboarding.",
        )
    return {
        "email": email,
        "firstname": first,
        "lastname": last,
        "vendor": vendor,
    }


def _notify_bff_onboard(bff_url: str | None, payload: dict) -> None:
    if not bff_url:
        raise HTTPException(
            status_code=400, detail="Instance BFF URL is required for onboarding."
        )
    url = f"{bff_url.rstrip('/')}/auth/auth/onboard"
    verify_setting: bool | str = settings.bff_verify_ssl
    if settings.bff_ca_bundle:
        verify_setting = settings.bff_ca_bundle
    try:
        global LAST_BFF_ERROR
        tls_context = _build_tls_context()
        if tls_context:
            adapter = TLSAdapter(tls_context)
            with requests.Session() as session:
                session.mount("https://", adapter)
                response = session.post(
                    url,
                    json=payload,
                    timeout=float(settings.bff_timeout_seconds),
                    verify=verify_setting,
                )
        else:
            response = requests.post(
                url,
                json=payload,
                timeout=float(settings.bff_timeout_seconds),
                verify=verify_setting,
            )
    except requests.RequestException as exc:
        LAST_BFF_ERROR = {
            "detail": f"BFF onboarding request failed: {exc}",
            "at": utc_now(),
        }
        raise HTTPException(
            status_code=502, detail=f"BFF onboarding request failed: {exc}"
        )
    if response.status_code >= 400:
        LAST_BFF_ERROR = {
            "detail": f"BFF onboarding failed: {response.status_code} {response.text}",
            "at": utc_now(),
        }
        raise HTTPException(
            status_code=502,
            detail=f"BFF onboarding failed: {response.status_code} {response.text}",
        )
    LAST_BFF_ERROR = None


def _email_domain(email: str | None) -> str | None:
    if not email:
        return None
    parts = email.strip().lower().split("@")
    if len(parts) != 2 or not parts[1]:
        return None
    return parts[1]


def _update_tenant_subscriber_flags(instance: dict, email: str | None) -> None:
    domain = _email_domain(email)
    if not domain:
        raise HTTPException(
            status_code=400, detail="Customer email domain is required for tenant updates."
        )
    required = [
        instance.get("pg_host"),
        instance.get("pg_user"),
        instance.get("pg_password"),
    ]
    if not all(required):
        raise HTTPException(
            status_code=400, detail="Instance Postgres credentials are missing."
        )
    try:
        conn = psycopg2.connect(
            host=instance.get("pg_host"),
            port=instance.get("pg_port") or 5432,
            user=instance.get("pg_user"),
            password=instance.get("pg_password"),
            dbname=settings.pg_database,
            sslmode=settings.pg_sslmode,
            connect_timeout=settings.connection_timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Postgres connection failed: {exc}")
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.subscriber
                SET "is_onboarded" = TRUE,
                    "is_analysisComplete" = TRUE,
                    "areControlsEnabled" = TRUE
                WHERE "name" = %s
                """,
                (domain,),
            )
            cursor.execute(
                """
                UPDATE public.tenant
                SET "license_config" = %s
                WHERE "name" = %s
                """,
                (json.dumps({"ai_axis_enabled": True}), domain),
            )
            conn.commit()
    except psycopg2.Error as exc:
        conn.rollback()
        detail = exc.pgerror or str(exc)
        raise HTTPException(
            status_code=400,
            detail=f"Tenant/subscriber update failed: {detail}",
        )
    finally:
        conn.close()




def _table_identifier(table: str) -> sql.Identifier:
    parts = [part for part in table.split(".") if part]
    if not parts:
        raise ValueError("Tenant table is not configured.")
    return sql.Identifier(*parts)


def _fetch_tenant_rows(instance: dict, keys: list[str]) -> dict[str, dict[str, str]]:
    if not keys:
        return {}
    required = [instance.get("pg_host"), instance.get("pg_user"), instance.get("pg_password")]
    if not all(required):
        return {}
    try:
        conn = psycopg2.connect(
            host=instance.get("pg_host"),
            port=instance.get("pg_port") or 5432,
            user=instance.get("pg_user"),
            password=instance.get("pg_password"),
            dbname=settings.pg_database,
            sslmode=settings.pg_sslmode,
            connect_timeout=settings.connection_timeout_seconds,
        )
    except Exception:
        return {}

    try:
        with conn.cursor() as cursor:
            query = sql.SQL(
                "SELECT {tenant_id}, {subscriber}, {name}, {match} FROM {table} "
                "WHERE lower({match}) = ANY(%s)"
            ).format(
                tenant_id=sql.Identifier(settings.tenant_id_column),
                subscriber=sql.Identifier(settings.tenant_subscriber_column),
                name=sql.Identifier(settings.tenant_name_column),
                match=sql.Identifier(settings.tenant_match_column),
                table=_table_identifier(settings.tenant_table),
            )
            cursor.execute(query, (keys,))
            rows = cursor.fetchall()
            return {
                row[3]: {
                    "tenant_id": str(row[0]),
                    "subscriber": str(row[1]),
                    "tenant_name": str(row[2]) if row[2] is not None else None,
                }
                for row in rows
                if row[3]
            }
    except Exception:
        return {}
    finally:
        conn.close()


def _fetch_all_tenants(instance: dict) -> list[dict]:
    required = [instance.get("pg_host"), instance.get("pg_user"), instance.get("pg_password")]
    if not all(required):
        return []
    try:
        conn = psycopg2.connect(
            host=instance.get("pg_host"),
            port=instance.get("pg_port") or 5432,
            user=instance.get("pg_user"),
            password=instance.get("pg_password"),
            dbname=settings.pg_database,
            sslmode=settings.pg_sslmode,
            connect_timeout=settings.connection_timeout_seconds,
        )
    except Exception:
        return []

    try:
        with conn.cursor() as cursor:
            query = sql.SQL(
                "SELECT {tenant_id}, {subscriber}, {name}, lower({match}) FROM {table}"
            ).format(
                tenant_id=sql.Identifier(settings.tenant_id_column),
                subscriber=sql.Identifier(settings.tenant_subscriber_column),
                name=sql.Identifier(settings.tenant_name_column),
                match=sql.Identifier(settings.tenant_match_column),
                table=_table_identifier(settings.tenant_table),
            )
            cursor.execute(query)
            rows = cursor.fetchall()
            return [
                {
                    "tenant_id": str(row[0]),
                    "subscriber": str(row[1]),
                    "tenant_name": str(row[2]) if row[2] is not None else None,
                    "match_value": (row[3] or "").lower(),
                }
                for row in rows
            ]
    except Exception:
        return []
    finally:
        conn.close()


def _fetch_internal_users(
    instance: dict, tenant_id: str, subscriber: str | None, account_type_value: str
) -> list[dict]:
    required = [instance.get("pg_host"), instance.get("pg_user"), instance.get("pg_password")]
    if not all(required):
        return []
    try:
        conn = psycopg2.connect(
            host=instance.get("pg_host"),
            port=instance.get("pg_port") or 5432,
            user=instance.get("pg_user"),
            password=instance.get("pg_password"),
            dbname=settings.pg_database,
            sslmode=settings.pg_sslmode,
            connect_timeout=settings.connection_timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Postgres connection failed: {exc}")

    try:
        with conn.cursor() as cursor:
            base = sql.SQL(
                "SELECT {user_id}, {first_name}, {last_name}, {username}, {email}, {account_type} "
                "FROM {table} WHERE {account_type} = {account_val} AND "
            ).format(
                user_id=sql.Identifier(settings.user_id_column),
                first_name=sql.Identifier(settings.user_first_name_column),
                last_name=sql.Identifier(settings.user_last_name_column),
                username=sql.Identifier(settings.user_username_column),
                email=sql.Identifier(settings.user_email_column),
                account_type=sql.Identifier(settings.user_account_type_column),
                account_val=sql.Placeholder(),
                table=_table_identifier(settings.user_table),
            )
            if settings.user_tenant_match_mode.lower() == "any":
                tenant_clause = sql.SQL("{} = ANY({})").format(
                    sql.Placeholder(), sql.Identifier(settings.user_tenant_column)
                )
            else:
                tenant_clause = sql.SQL("{tenant_col} = {tenant_val}").format(
                    tenant_col=sql.Identifier(settings.user_tenant_column),
                    tenant_val=sql.Placeholder(),
                )
            def run_query(with_subscriber: bool) -> list[tuple]:
                query = base + tenant_clause
                params: list[object] = [account_type_value, tenant_id]
                if with_subscriber and subscriber:
                    query += sql.SQL(" AND {subscriber_col} = {subscriber_val}").format(
                        subscriber_col=sql.Identifier(settings.user_subscriber_column),
                        subscriber_val=sql.Placeholder(),
                    )
                    params.append(subscriber)
                cursor.execute(query, params)
                return cursor.fetchall()

            rows = run_query(with_subscriber=True)
            if (
                subscriber
                and not rows
                and account_type_value == settings.user_account_type_oauth_value
            ):
                rows = run_query(with_subscriber=False)
            return [
                {
                    "id": str(row[0]) if row[0] is not None else None,
                    "name": (
                        _compose_name(
                            str(row[1]) if row[1] is not None else None,
                            str(row[2]) if row[2] is not None else None,
                        )
                        or (str(row[3]) if row[3] is not None else None)
                        or (str(row[4]) if row[4] is not None else None)
                    ),
                    "email": str(row[4]) if row[4] is not None else None,
                    "account_type": str(row[5]) if row[5] is not None else None,
                }
                for row in rows
            ]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"User lookup failed: {exc}")
    finally:
        conn.close()


def _match_clause(column: str, match_mode: str, value: str) -> tuple[sql.SQL, list[object]]:
    if match_mode.lower() == "any":
        clause = sql.SQL("{} = ANY({})").format(
            sql.Placeholder(), sql.Identifier(column)
        )
    else:
        clause = sql.SQL("{tenant_col} = {tenant_val}").format(
            tenant_col=sql.Identifier(column),
            tenant_val=sql.Placeholder(),
        )
    return clause, [value]


def _tenant_match_clause(tenant_id: str) -> tuple[sql.SQL, list[object]]:
    return _match_clause(
        settings.user_tenant_column, settings.user_tenant_match_mode, tenant_id
    )


def _fetch_ids_from_table(
    conn,
    table: str,
    id_column: str,
    name_column: str | None,
    tenant_id: str,
    tenant_column: str,
    tenant_match_mode: str,
    subscriber_column: str | None,
    subscriber: str | None,
    names: list[str] | None,
) -> list[str]:
    if not table or not id_column or not tenant_column:
        return []
    columns_to_try = [tenant_column] + [
        candidate
        for candidate in ("tenantId", "tenantIds")
        if candidate and candidate != tenant_column
    ]
    last_exc: Exception | None = None
    for candidate in columns_to_try:
        try:
            clauses: list[sql.SQL] = []
            params: list[object] = []
            tenant_clause, tenant_params = _match_clause(
                candidate, tenant_match_mode, tenant_id
            )
            clauses.append(tenant_clause)
            params.extend(tenant_params)
            if subscriber_column and subscriber:
                clauses.append(
                    sql.SQL("{subscriber_col} = {subscriber_val}").format(
                        subscriber_col=sql.Identifier(subscriber_column),
                        subscriber_val=sql.Placeholder(),
                    )
                )
                params.append(subscriber)
            if names:
                if not name_column:
                    raise ValueError("Name column is required for role/group filters.")
                clauses.append(
                    sql.SQL("{name_col} = ANY({name_val})").format(
                        name_col=sql.Identifier(name_column),
                        name_val=sql.Placeholder(),
                    )
                )
                params.append(names)
            query = sql.SQL("SELECT {id_col} FROM {table}").format(
                id_col=sql.Identifier(id_column),
                table=_table_identifier(table),
            )
            if clauses:
                query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)
            if name_column:
                query += sql.SQL(" ORDER BY {name_col}").format(
                    name_col=sql.Identifier(name_column)
                )
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
            return [
                str(row[0])
                for row in rows
                if row and row[0] is not None and str(row[0])
            ]
        except Exception as exc:
            last_exc = exc
            message = str(exc).lower()
            if "does not exist" in message and "column" in message:
                continue
            logger.error("Role/group lookup failed for %s: %s", table, exc)
            return []
    if last_exc:
        logger.error("Role/group lookup failed for %s: %s", table, last_exc)
    return []


def _fetch_role_ids(conn, tenant_id: str, subscriber: str | None) -> list[str]:
    return _fetch_ids_from_table(
        conn,
        settings.role_table,
        settings.role_id_column,
        settings.role_name_column,
        tenant_id,
        settings.role_tenant_column,
        settings.role_tenant_match_mode,
        settings.role_subscriber_column,
        subscriber,
        settings.default_role_names,
    )


def _fetch_group_ids(conn, tenant_id: str, subscriber: str | None) -> list[str]:
    return _fetch_ids_from_table(
        conn,
        settings.group_table,
        settings.group_id_column,
        settings.group_name_column,
        tenant_id,
        settings.group_tenant_column,
        settings.group_tenant_match_mode,
        settings.group_subscriber_column,
        subscriber,
        settings.default_group_names,
    )


def _load_instances(db, instance_ids: set[str] | None = None) -> dict[str, dict]:
    if instance_ids is not None and not instance_ids:
        return {}
    if instance_ids is None:
        rows = db.execute(
            """
            SELECT id, name, pg_host, pg_port, pg_user, pg_password
            FROM instances
            """
        ).fetchall()
        return {row["id"]: _row_to_dict(row) for row in rows}
    placeholders = ", ".join(["?"] * len(instance_ids))
    rows = db.execute(
        f"""
        SELECT id, name, pg_host, pg_port, pg_user, pg_password
        FROM instances WHERE id IN ({placeholders})
        """,
        tuple(instance_ids),
    ).fetchall()
    return {row["id"]: _row_to_dict(row) for row in rows}


def _load_cached_tenants(db, instance_id: str) -> tuple[list[dict], str | None]:
    rows = db.execute(
        """
        SELECT match_value, tenant_id, tenant_name, subscriber, fetched_at
        FROM tenant_cache WHERE instance_id = ?
        """,
        (instance_id,),
    ).fetchall()
    if not rows:
        return [], None
    fetched_at = rows[0]["fetched_at"]
    return [
        {
            "match_value": row["match_value"],
            "tenant_id": row["tenant_id"],
            "tenant_name": row["tenant_name"],
            "subscriber": row["subscriber"],
        }
        for row in rows
    ], fetched_at


def _save_cached_tenants(db, instance_id: str, tenants: list[dict]) -> None:
    if not tenants:
        return
    fetched_at = utc_now()
    unique: dict[str, dict] = {}
    for tenant in tenants:
        match_value = (tenant.get("match_value") or "").strip().lower()
        if not match_value or match_value in unique:
            continue
        unique[match_value] = tenant
    if not unique:
        return
    db.execute("DELETE FROM tenant_cache WHERE instance_id = ?", (instance_id,))
    db.executemany(
        """
        INSERT INTO tenant_cache (
            instance_id, match_value, tenant_id, tenant_name, subscriber, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            (
                instance_id,
                match_value,
                tenant.get("tenant_id"),
                tenant.get("tenant_name"),
                tenant.get("subscriber"),
                fetched_at,
            )
            for match_value, tenant in unique.items()
        ],
    )
    db.commit()


def _is_cache_fresh(fetched_at: str | None) -> bool:
    if not fetched_at:
        return False
    try:
        parsed = datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - parsed).total_seconds()
    return age <= settings.tenant_cache_ttl_seconds


def _is_internal_user_cache_fresh(fetched_at: str | None) -> bool:
    if not fetched_at:
        return False
    try:
        parsed = datetime.fromisoformat(fetched_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age = (datetime.now(timezone.utc) - parsed).total_seconds()
    return age <= settings.internal_user_cache_ttl_seconds


def _clear_internal_user_cache(
    db, instance_id: str, tenant_id: str, subscriber: str, account_type: str
) -> None:
    db.execute(
        """
        DELETE FROM internal_user_cache
        WHERE instance_id = ? AND tenant_id = ? AND subscriber = ? AND account_type = ?
        """,
        (instance_id, tenant_id, subscriber, account_type),
    )


def _resolve_internal_user_tenant(
    instance: dict, db, payload: InternalUserCreate
) -> tuple[str, str | None]:
    if payload.tenant_id:
        tenant_id = payload.tenant_id
        subscriber = payload.subscriber
        if not subscriber:
            cached = db.execute(
                """
                SELECT subscriber FROM tenant_cache
                WHERE instance_id = ? AND tenant_id = ?
                LIMIT 1
                """,
                (instance.get("id") or payload.instance_id, tenant_id),
            ).fetchone()
            if cached:
                subscriber = cached["subscriber"]
        return tenant_id, subscriber
    match_column = settings.tenant_match_column.lower()
    if match_column in {"email", "contact_email"}:
        match_value = (payload.match_email or payload.match_name or "").strip().lower()
    else:
        match_value = (payload.match_name or payload.match_email or "").strip().lower()
    if not match_value:
        raise HTTPException(status_code=400, detail="Tenant match value is required.")
    tenant_rows = _fetch_tenant_rows(instance, [match_value])
    info = tenant_rows.get(match_value)
    if not info:
        raise HTTPException(status_code=404, detail="Tenant not found for internal user.")
    return info["tenant_id"], info.get("subscriber")


def _fetch_internal_user_defaults(
    conn, tenant_id: str, subscriber: str | None, account_type_value: str
) -> dict | None:
    with conn.cursor() as cursor:
        tenant_clause, tenant_params = _tenant_match_clause(tenant_id)
        query = sql.SQL(
            "SELECT {role_ids}, {group_ids}, {status}, {verification}, "
            "{createdby}, {updatedby}, {email_sent} FROM {table} "
            "WHERE {account_type_col} = {account_val} AND "
        ).format(
            role_ids=sql.Identifier(settings.user_role_ids_column),
            group_ids=sql.Identifier(settings.user_group_ids_column),
            status=sql.Identifier(settings.user_status_column),
            verification=sql.Identifier(settings.user_verification_column),
            createdby=sql.Identifier(settings.user_createdby_column),
            updatedby=sql.Identifier(settings.user_updatedby_column),
            email_sent=sql.Identifier(settings.user_email_sent_column),
            table=_table_identifier(settings.user_table),
            account_type_col=sql.Identifier(settings.user_account_type_column),
            account_val=sql.Placeholder(),
        )
        params: list[object] = [account_type_value]
        query += tenant_clause
        params.extend(tenant_params)
        if subscriber:
            query += sql.SQL(" AND {subscriber_col} = {subscriber_val}").format(
                subscriber_col=sql.Identifier(settings.user_subscriber_column),
                subscriber_val=sql.Placeholder(),
            )
            params.append(subscriber)
        query += sql.SQL(" LIMIT 1")
        cursor.execute(query, params)
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "role_ids": row[0] or [],
            "group_ids": row[1] or [],
            "status": row[2],
            "verification_status": row[3],
            "createdby": row[4],
            "updatedby": row[5],
            "email_sent": row[6],
        }


def _load_cached_internal_users(
    db, instance_id: str, tenant_id: str, subscriber: str, account_type: str
) -> tuple[list[dict], str | None]:
    rows = db.execute(
        """
        SELECT user_id, name, email, account_type, fetched_at
        FROM internal_user_cache
        WHERE instance_id = ? AND tenant_id = ? AND subscriber = ? AND account_type = ?
        """,
        (instance_id, tenant_id, subscriber, account_type),
    ).fetchall()
    if not rows:
        return [], None
    fetched_at = rows[0]["fetched_at"]
    return [
        {
            "id": row["user_id"],
            "name": row["name"],
            "email": row["email"],
            "account_type": row["account_type"],
        }
        for row in rows
    ], fetched_at


def _save_cached_internal_users(
    db,
    instance_id: str,
    tenant_id: str,
    subscriber: str,
    account_type: str,
    users: list[dict],
) -> None:
    fetched_at = utc_now()
    db.execute(
        """
        DELETE FROM internal_user_cache
        WHERE instance_id = ? AND tenant_id = ? AND subscriber = ? AND account_type = ?
        """,
        (instance_id, tenant_id, subscriber, account_type),
    )
    if users:
        db.executemany(
            """
            INSERT INTO internal_user_cache (
                instance_id, tenant_id, subscriber, user_id, name, email, account_type, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    instance_id,
                    tenant_id,
                    subscriber,
                    user_row.get("id"),
                    user_row.get("name"),
                    user_row.get("email"),
                    account_type,
                    fetched_at,
                )
                for user_row in users
                if user_row.get("id")
            ],
        )
    db.commit()


def _clear_tenant_cache(db, instance_id: str) -> None:
    db.execute("DELETE FROM tenant_cache WHERE instance_id = ?", (instance_id,))


def _attach_tenant_info(customers: list[dict], instances: dict[str, dict]) -> None:
    for customer in customers:
        customer["tenant_name"] = None
        customer["tenant_id"] = None
        customer["subscriber"] = None
    for instance_id, instance in instances.items():
        match_column = settings.tenant_match_column.lower()
        if match_column in {"email", "contact_email"}:
            keys = [
                (customer.get("contact_email") or "").lower()
                for customer in customers
                if customer.get("instance_id") == instance_id and customer.get("contact_email")
            ]
        else:
            keys = [
                (customer.get("name") or "").lower()
                for customer in customers
                if customer.get("instance_id") == instance_id and customer.get("name")
            ]
        keys = [key for key in keys if key]
        if not keys:
            continue
        tenant_rows = _fetch_tenant_rows(instance, keys)
        for customer in customers:
            if customer.get("instance_id") != instance_id:
                continue
            match_key = (
                (customer.get("contact_email") or "").lower()
                if match_column in {"email", "contact_email"}
                else (customer.get("name") or "").lower()
            )
            info = tenant_rows.get(match_key or "")
            if info:
                customer["tenant_name"] = info.get("tenant_name")
                customer["tenant_id"] = info["tenant_id"]
                customer["subscriber"] = info["subscriber"]


def _expand_customers_with_tenants(
    customers: list[dict],
    instances: dict[str, dict],
    db,
    refresh: bool,
) -> None:
    match_column = settings.tenant_match_column.lower()
    for customer in customers:
        customer["tenant_name"] = customer.get("tenant_name")
        customer["tenant_id"] = customer.get("tenant_id")
        customer["subscriber"] = customer.get("subscriber")

    for instance_id, instance in instances.items():
        cached_tenants, fetched_at = _load_cached_tenants(db, instance_id)
        tenants: list[dict] = []
        cache_fresh = _is_cache_fresh(fetched_at)
        if not refresh and cache_fresh and cached_tenants:
            tenants = cached_tenants
        else:
            fetched = _fetch_all_tenants(instance)
            if fetched:
                _save_cached_tenants(db, instance_id, fetched)
                tenants = fetched
            else:
                tenants = cached_tenants
        if not tenants:
            continue
        tenant_map = {tenant["match_value"]: tenant for tenant in tenants if tenant["match_value"]}
        matched_keys: set[str] = set()
        matched_tenants: set[str] = set()

        for customer in customers:
            if customer.get("instance_id") != instance_id:
                continue
            match_key = (
                (customer.get("contact_email") or "").lower()
                if match_column in {"email", "contact_email"}
                else (customer.get("name") or "").lower()
            )
            if match_key:
                matched_keys.add(match_key)
            info = tenant_map.get(match_key or "")
            if info:
                customer["tenant_name"] = info.get("tenant_name")
                customer["tenant_id"] = info["tenant_id"]
                customer["subscriber"] = info["subscriber"]
                matched_tenants.add(info["tenant_id"])

        for tenant in tenants:
            if tenant["tenant_id"] in matched_tenants:
                continue
            if tenant["match_value"] and tenant["match_value"] in matched_keys:
                continue
            customers.append(
                {
                    "id": f"tenant:{instance_id}:{tenant['tenant_id']}",
                    "name": tenant.get("tenant_name") or tenant["match_value"] or "—",
                    "first_name": None,
                    "last_name": None,
                    "vendor": None,
                    "contact_email": None,
                    "instance_id": instance_id,
                    "instance_name": instance.get("name"),
                    "tenant_name": tenant.get("tenant_name"),
                    "tenant_id": tenant.get("tenant_id"),
                    "subscriber": tenant.get("subscriber"),
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                }
            )


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/auth/login")
async def auth_login(request: Request):
    return await login(request)


@app.get("/auth/callback")
async def auth_callback(request: Request):
    return await callback(request)


@app.get("/auth/logout")
async def auth_logout(request: Request):
    request.session.clear()
    return JSONResponse({"ok": True})


@app.get("/api/session", response_model=SessionOut)
def session_info(request: Request) -> SessionOut:
    user = request.session.get("user")
    return SessionOut(authenticated=bool(user), user=user)


@app.get("/api/config")
def public_config() -> dict:
    return {
        "ms_client_id": settings.ms_client_id,
        "ms_tenant_id": settings.ms_tenant_id,
    }


@app.post("/auth/token")
def auth_token(payload: TokenExchangeRequest, request: Request) -> dict:
    user = create_session_from_id_token(payload.id_token, payload.groups)
    request.session["user"] = user
    return {"ok": True, "user": user}


@app.post("/api/test/postgres")
def test_postgres(
    payload: PostgresTestRequest, user: dict = Depends(require_user), db=Depends(get_db)
) -> dict:
    instance = None
    if payload.instance_id:
        instance = db.execute(
            """
            SELECT pg_host, pg_port, pg_user, pg_password
            FROM instances WHERE id = ?
            """,
            (payload.instance_id,),
        ).fetchone()
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found.")
    host = payload.host or (instance["pg_host"] if instance else None)
    port = payload.port or (instance["pg_port"] if instance else None) or 5432
    user_name = payload.user or (instance["pg_user"] if instance else None)
    password = payload.password or (instance["pg_password"] if instance else None)
    if not host or not user_name or not password:
        raise HTTPException(
            status_code=400, detail="Postgres host, user, and password are required."
        )
    dbname = payload.database or settings.pg_database
    sslmode = payload.sslmode or settings.pg_sslmode
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user_name,
            password=password,
            dbname=dbname,
            sslmode=sslmode,
            connect_timeout=settings.connection_timeout_seconds,
        )
        conn.close()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Postgres connection failed: {exc}")
    return {"ok": True, "message": "Postgres connection successful."}


@app.post("/api/test/neo4j")
def test_neo4j(
    payload: Neo4jTestRequest, user: dict = Depends(require_user), db=Depends(get_db)
) -> dict:
    instance = None
    if payload.instance_id:
        instance = db.execute(
            """
            SELECT neo4j_host, neo4j_port, neo4j_user, neo4j_password
            FROM instances WHERE id = ?
            """,
            (payload.instance_id,),
        ).fetchone()
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found.")
    host = payload.host or (instance["neo4j_host"] if instance else None)
    port = payload.port or (instance["neo4j_port"] if instance else None) or 7687
    if not host:
        raise HTTPException(status_code=400, detail="Neo4j host is required.")
    try:
        conn = socket.create_connection(
            (host, port),
            timeout=settings.connection_timeout_seconds,
        )
        conn.close()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Neo4j connection failed: {exc}")
    return {"ok": True, "message": "Neo4j connection successful."}


@app.get("/api/instances", response_model=list[InstanceOut])
def list_instances(user: dict = Depends(require_user), db=Depends(get_db)):
    rows = db.execute(
        """
        SELECT id, name, base_url AS bff_url, status,
               pg_host, pg_port, pg_user, pg_password,
               neo4j_host, neo4j_port, neo4j_user, neo4j_password,
               created_at, updated_at
        FROM instances
        """
    ).fetchall()
    return [InstanceOut(**_row_to_dict(row)) for row in rows]


@app.post("/api/instances", response_model=InstanceOut, status_code=status.HTTP_201_CREATED)
def create_instance(
    payload: InstanceCreate, user: dict = Depends(require_user), db=Depends(get_db)
):
    instance_id = str(uuid4())
    now = utc_now()
    db.execute(
        """
        INSERT INTO instances (
            id, name, base_url, status,
            pg_host, pg_port, pg_user, pg_password,
            neo4j_host, neo4j_port, neo4j_user, neo4j_password,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            instance_id,
            payload.name,
            payload.bff_url,
            payload.status,
            payload.pg_host,
            payload.pg_port,
            payload.pg_user,
            payload.pg_password,
            payload.neo4j_host,
            payload.neo4j_port,
            payload.neo4j_user,
            payload.neo4j_password,
            now,
            now,
        ),
    )
    db.commit()
    row = db.execute(
        """
        SELECT id, name, base_url AS bff_url, status,
               pg_host, pg_port, pg_user, pg_password,
               neo4j_host, neo4j_port, neo4j_user, neo4j_password,
               created_at, updated_at
        FROM instances WHERE id = ?
        """,
        (instance_id,),
    ).fetchone()
    return InstanceOut(**_row_to_dict(row))


@app.put("/api/instances/{instance_id}", response_model=InstanceOut)
def update_instance(
    instance_id: str,
    payload: InstanceUpdate,
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    row = db.execute(
        """
        SELECT id, name, base_url AS bff_url, status,
               pg_host, pg_port, pg_user, pg_password,
               neo4j_host, neo4j_port, neo4j_user, neo4j_password,
               created_at, updated_at
        FROM instances WHERE id = ?
        """,
        (instance_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Instance not found.")
    current = _row_to_dict(row)
    updated = {
        "name": payload.name if payload.name is not None else current["name"],
        "bff_url": payload.bff_url if payload.bff_url is not None else current["bff_url"],
        "status": payload.status if payload.status is not None else current["status"],
        "pg_host": payload.pg_host if payload.pg_host is not None else current["pg_host"],
        "pg_port": payload.pg_port if payload.pg_port is not None else current["pg_port"],
        "pg_user": payload.pg_user if payload.pg_user is not None else current["pg_user"],
        "pg_password": payload.pg_password
        if payload.pg_password is not None
        else current["pg_password"],
        "neo4j_host": payload.neo4j_host
        if payload.neo4j_host is not None
        else current["neo4j_host"],
        "neo4j_port": payload.neo4j_port
        if payload.neo4j_port is not None
        else current["neo4j_port"],
        "neo4j_user": payload.neo4j_user
        if payload.neo4j_user is not None
        else current["neo4j_user"],
        "neo4j_password": payload.neo4j_password
        if payload.neo4j_password is not None
        else current["neo4j_password"],
        "updated_at": utc_now(),
    }
    db.execute(
        """
        UPDATE instances
        SET name = ?, base_url = ?, status = ?,
            pg_host = ?, pg_port = ?, pg_user = ?, pg_password = ?,
            neo4j_host = ?, neo4j_port = ?, neo4j_user = ?, neo4j_password = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            updated["name"],
            updated["bff_url"],
            updated["status"],
            updated["pg_host"],
            updated["pg_port"],
            updated["pg_user"],
            updated["pg_password"],
            updated["neo4j_host"],
            updated["neo4j_port"],
            updated["neo4j_user"],
            updated["neo4j_password"],
            updated["updated_at"],
            instance_id,
        ),
    )
    _clear_tenant_cache(db, instance_id)
    db.commit()
    row = db.execute(
        """
        SELECT id, name, base_url AS bff_url, status,
               pg_host, pg_port, pg_user, pg_password,
               neo4j_host, neo4j_port, neo4j_user, neo4j_password,
               created_at, updated_at
        FROM instances WHERE id = ?
        """,
        (instance_id,),
    ).fetchone()
    return InstanceOut(**_row_to_dict(row))


@app.delete("/api/instances/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_instance(
    instance_id: str, user: dict = Depends(require_user), db=Depends(get_db)
):
    row = db.execute("SELECT id FROM instances WHERE id = ?", (instance_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Instance not found.")
    db.execute("UPDATE customers SET instance_id = NULL WHERE instance_id = ?", (instance_id,))
    db.execute("DELETE FROM instances WHERE id = ?", (instance_id,))
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


@app.get("/api/customers", response_model=list[CustomerOut])
def list_customers(
    refresh: bool = Query(False),
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    rows = db.execute(
        """
        SELECT customers.id, customers.name, customers.first_name, customers.last_name,
               customers.department, customers.vendor, customers.contact_email, customers.instance_id,
               customers.created_at, customers.updated_at, instances.name AS instance_name
        FROM customers
        LEFT JOIN instances ON customers.instance_id = instances.id
        """
    ).fetchall()
    customers = [_row_to_dict(row) for row in rows]
    instances = _load_instances(db)
    _expand_customers_with_tenants(customers, instances, db, refresh)
    return [CustomerOut(**customer) for customer in customers]


@app.get("/api/customers/{customer_id}/internal-users", response_model=list[InternalUserOut])
def list_internal_users(
    customer_id: str,
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    row = db.execute(
        """
        SELECT id, name, first_name, last_name, vendor, contact_email, instance_id
        FROM customers WHERE id = ?
        """,
        (customer_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found.")
    customer = _row_to_dict(row)
    instance_id = customer.get("instance_id")
    if not instance_id:
        return []
    instances = _load_instances(db, {instance_id})
    instance = instances.get(instance_id)
    if not instance:
        return []
    _attach_tenant_info([customer], instances)
    tenant_id = customer.get("tenant_id")
    subscriber = customer.get("subscriber")
    if not tenant_id or not subscriber:
        return []
    users = _fetch_internal_users(
        instance, tenant_id, subscriber, settings.user_account_type_value
    )
    return [InternalUserOut(**user_row) for user_row in users]


@app.post("/api/customers/{customer_id}/neo4j")
def push_customer_to_neo4j(
    customer_id: str,
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    if customer_id.startswith("tenant:"):
        raise HTTPException(status_code=400, detail="Select a saved customer to push.")
    row = db.execute(
        """
        SELECT id, name, first_name, last_name, department, vendor,
               contact_email, instance_id
        FROM customers WHERE id = ?
        """,
        (customer_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found.")
    customer = _row_to_dict(row)
    instance_id = customer.get("instance_id")
    if not instance_id:
        raise HTTPException(status_code=400, detail="Customer has no instance assigned.")
    instance_row = db.execute(
        """
        SELECT id, name, neo4j_host, neo4j_port, neo4j_user, neo4j_password
        FROM instances WHERE id = ?
        """,
        (instance_id,),
    ).fetchone()
    if not instance_row:
        raise HTTPException(status_code=404, detail="Instance not found.")
    instance = _row_to_dict(instance_row)
    instances = _load_instances(db, {instance_id})
    _attach_tenant_info([customer], instances)
    tenant_id = customer.get("tenant_id")
    subscriber = customer.get("subscriber")
    tenant_name = customer.get("tenant_name") or tenant_id
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Tenant details are missing.")
    _push_customer_to_neo4j(instance, customer, tenant_id, subscriber, tenant_name or "")
    return {"ok": True}


@app.get("/api/internal-users", response_model=list[InternalUserOut])
def list_internal_users_by_tenant(
    instance_id: str = Query(...),
    tenant_id: str = Query(...),
    subscriber: str | None = Query(None),
    refresh: bool = Query(False),
    account_type: str | None = Query(None),
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    row = db.execute(
        """
        SELECT pg_host, pg_port, pg_user, pg_password
        FROM instances WHERE id = ?
        """,
        (instance_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Instance not found.")
    instance = _row_to_dict(row)
    resolved_subscriber = subscriber
    if not resolved_subscriber:
        cached = db.execute(
            """
            SELECT subscriber FROM tenant_cache
            WHERE instance_id = ? AND tenant_id = ?
            LIMIT 1
            """,
            (instance_id, tenant_id),
        ).fetchone()
        if cached:
            resolved_subscriber = cached["subscriber"]
    subscriber_key = (resolved_subscriber or "").strip()
    account_type_value = account_type or settings.user_account_type_value
    cached_users, fetched_at = _load_cached_internal_users(
        db, instance_id, tenant_id, subscriber_key, account_type_value
    )
    if not refresh and cached_users and _is_internal_user_cache_fresh(fetched_at):
        return [InternalUserOut(**user_row) for user_row in cached_users]
    users = _fetch_internal_users(instance, tenant_id, resolved_subscriber, account_type_value)
    _save_cached_internal_users(
        db, instance_id, tenant_id, subscriber_key, account_type_value, users
    )
    return [InternalUserOut(**user_row) for user_row in users]


@app.post("/api/internal-users", response_model=InternalUserOut)
def create_internal_user(
    payload: InternalUserCreate,
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    row = db.execute(
        """
        SELECT id, pg_host, pg_port, pg_user, pg_password
        FROM instances WHERE id = ?
        """,
        (payload.instance_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Instance not found.")
    instance = _row_to_dict(row)
    required = [instance.get("pg_host"), instance.get("pg_user"), instance.get("pg_password")]
    if not all(required):
        raise HTTPException(
            status_code=400, detail="Instance Postgres credentials are missing."
        )
    account_type_value = payload.account_type or settings.user_account_type_value
    raw_password = (payload.password or "").strip()
    if account_type_value == settings.user_account_type_value:
        if not raw_password:
            raise HTTPException(status_code=400, detail="Password is required.")
        if len(raw_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    else:
        if raw_password and len(raw_password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
        if not raw_password:
            raw_password = uuid4().hex
    tenant_id, subscriber = _resolve_internal_user_tenant(instance, db, payload)
    subscriber_key = (subscriber or "").strip()
    try:
        conn = psycopg2.connect(
            host=instance.get("pg_host"),
            port=instance.get("pg_port") or 5432,
            user=instance.get("pg_user"),
            password=instance.get("pg_password"),
            dbname=settings.pg_database,
            sslmode=settings.pg_sslmode,
            connect_timeout=settings.connection_timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Postgres connection failed: {exc}")

    hashed = bcrypt.hashpw(raw_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    try:
        defaults = _fetch_internal_user_defaults(conn, tenant_id, subscriber, account_type_value)
        role_ids = (defaults or {}).get("role_ids") or []
        group_ids = (defaults or {}).get("group_ids") or []
        if not role_ids:
            role_ids = _fetch_role_ids(conn, tenant_id, subscriber)
        if not group_ids:
            group_ids = _fetch_group_ids(conn, tenant_id, subscriber)
        status_value = (defaults or {}).get("status") or settings.internal_user_default_status
        verification_value = (defaults or {}).get("verification_status") or (
            settings.internal_user_default_verification_status
        )
        createdby_value = (defaults or {}).get("createdby") or (
            settings.internal_user_default_createdby
        )
        updatedby_value = (defaults or {}).get("updatedby") or (
            settings.internal_user_default_updatedby
        )
        email_sent_value = (
            (defaults or {}).get("email_sent")
            if defaults and defaults.get("email_sent") is not None
            else settings.internal_user_default_email_sent
        )
        with conn.cursor() as cursor:
            query = sql.SQL(
                "INSERT INTO {table} ("
                "{first_name}, {last_name}, {username}, {email}, {password}, "
                "{subscriber_col}, {tenant_col}, {role_col}, {group_col}, "
                "{status_col}, {verification_col}, {createdby_col}, {updatedby_col}, "
                "{account_type_col}, {email_sent_col}"
                ") VALUES ("
                "{first_val}, {last_val}, {username_val}, {email_val}, {password_val}, "
                "{subscriber_val}, {tenant_val}, {role_val}, {group_val}, "
                "{status_val}, {verification_val}, {createdby_val}, {updatedby_val}, "
                "{account_type_val}, {email_sent_val}"
                ") RETURNING {user_id_col}"
            ).format(
                table=_table_identifier(settings.user_table),
                first_name=sql.Identifier(settings.user_first_name_column),
                last_name=sql.Identifier(settings.user_last_name_column),
                username=sql.Identifier(settings.user_username_column),
                email=sql.Identifier(settings.user_email_column),
                password=sql.Identifier(settings.user_password_column),
                subscriber_col=sql.Identifier(settings.user_subscriber_column),
                tenant_col=sql.Identifier(settings.user_tenant_column),
                role_col=sql.Identifier(settings.user_role_ids_column),
                group_col=sql.Identifier(settings.user_group_ids_column),
                status_col=sql.Identifier(settings.user_status_column),
                verification_col=sql.Identifier(settings.user_verification_column),
                createdby_col=sql.Identifier(settings.user_createdby_column),
                updatedby_col=sql.Identifier(settings.user_updatedby_column),
                account_type_col=sql.Identifier(settings.user_account_type_column),
                email_sent_col=sql.Identifier(settings.user_email_sent_column),
                first_val=sql.Placeholder(),
                last_val=sql.Placeholder(),
                username_val=sql.Placeholder(),
                email_val=sql.Placeholder(),
                password_val=sql.Placeholder(),
                subscriber_val=sql.Placeholder(),
                tenant_val=sql.Placeholder(),
                role_val=sql.Placeholder(),
                group_val=sql.Placeholder(),
                status_val=sql.Placeholder(),
                verification_val=sql.Placeholder(),
                createdby_val=sql.Placeholder(),
                updatedby_val=sql.Placeholder(),
                account_type_val=sql.Placeholder(),
                email_sent_val=sql.Placeholder(),
                user_id_col=sql.Identifier(settings.user_id_column),
            )
            cursor.execute(
                query,
                (
                    payload.first_name.strip(),
                    payload.last_name.strip(),
                    payload.username.strip(),
                    payload.email.strip(),
                    hashed,
                    subscriber,
                    [tenant_id],
                    role_ids,
                    group_ids,
                    status_value,
                    verification_value,
                    createdby_value,
                    updatedby_value,
                    account_type_value,
                    email_sent_value,
                ),
            )
            user_id = cursor.fetchone()[0]
            conn.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Internal user create failed: {exc}")
    finally:
        conn.close()
    _clear_internal_user_cache(
        db, payload.instance_id, tenant_id, subscriber_key, account_type_value
    )
    return InternalUserOut(
        id=str(user_id),
        name=_compose_name(payload.first_name, payload.last_name),
        email=payload.email,
        account_type=account_type_value,
    )


@app.post("/api/internal-users/password")
def update_internal_user_password(
    payload: InternalUserPasswordUpdate,
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    if not payload.new_password.strip():
        raise HTTPException(status_code=400, detail="Password is required.")
    row = db.execute(
        """
        SELECT pg_host, pg_port, pg_user, pg_password
        FROM instances WHERE id = ?
        """,
        (payload.instance_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Instance not found.")
    instance = _row_to_dict(row)
    required = [instance.get("pg_host"), instance.get("pg_user"), instance.get("pg_password")]
    if not all(required):
        raise HTTPException(
            status_code=400, detail="Instance Postgres credentials are missing."
        )
    try:
        conn = psycopg2.connect(
            host=instance.get("pg_host"),
            port=instance.get("pg_port") or 5432,
            user=instance.get("pg_user"),
            password=instance.get("pg_password"),
            dbname=settings.pg_database,
            sslmode=settings.pg_sslmode,
            connect_timeout=settings.connection_timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Postgres connection failed: {exc}")

    hashed = bcrypt.hashpw(payload.new_password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )
    try:
        with conn.cursor() as cursor:
            tenant_clause, tenant_params = _tenant_match_clause(payload.tenant_id)
            query = sql.SQL(
                "UPDATE {table} SET {password_col} = {password_val} "
                "WHERE {user_id_col} = {user_id_val} AND {account_type_col} = {account_val} AND "
            ).format(
                table=_table_identifier(settings.user_table),
                password_col=sql.Identifier(settings.user_password_column),
                password_val=sql.Placeholder(),
                user_id_col=sql.Identifier(settings.user_id_column),
                user_id_val=sql.Placeholder(),
                account_type_col=sql.Identifier(settings.user_account_type_column),
                account_val=sql.Placeholder(),
            )
            params: list[object] = [
                hashed,
                payload.user_id,
                settings.user_account_type_value,
            ]
            query += tenant_clause
            params.extend(tenant_params)
            if payload.subscriber:
                query += sql.SQL(" AND {subscriber_col} = {subscriber_val}").format(
                    subscriber_col=sql.Identifier(settings.user_subscriber_column),
                    subscriber_val=sql.Placeholder(),
                )
                params.append(payload.subscriber)
            cursor.execute(query, params)
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found for tenant.")
            conn.commit()
    finally:
        conn.close()
    return {"ok": True}


@app.post("/api/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    instance: dict | None = None
    bff_payload: dict | None = None
    if payload.instance_id:
        instance_row = db.execute(
            """
            SELECT id, base_url, pg_host, pg_port, pg_user, pg_password
            FROM instances WHERE id = ?
            """,
            (payload.instance_id,),
        ).fetchone()
        if not instance_row:
            raise HTTPException(status_code=400, detail="Instance does not exist.")
        instance = _row_to_dict(instance_row)
        bff_payload = _build_bff_payload(payload)
    full_name = _build_customer_name(payload)
    if not full_name:
        raise HTTPException(
            status_code=400, detail="Customer first name and last name are required."
        )
    if instance and bff_payload:
        _notify_bff_onboard(instance.get("base_url"), bff_payload)
        _update_tenant_subscriber_flags(instance, payload.contact_email)
    customer_id = str(uuid4())
    now = utc_now()
    db.execute(
        """
        INSERT INTO customers (
            id, name, first_name, last_name, department, vendor,
            contact_email, instance_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            full_name,
            payload.first_name,
            payload.last_name,
            payload.department,
            payload.vendor,
            payload.contact_email,
            payload.instance_id,
            now,
            now,
        ),
    )
    db.commit()
    row = db.execute(
        """
        SELECT customers.id, customers.name, customers.first_name, customers.last_name,
               customers.department, customers.vendor, customers.contact_email, customers.instance_id,
               customers.created_at, customers.updated_at, instances.name AS instance_name
        FROM customers
        LEFT JOIN instances ON customers.instance_id = instances.id
        WHERE customers.id = ?
        """,
        (customer_id,),
    ).fetchone()
    customer = _row_to_dict(row)
    instances = _load_instances(db, {customer.get("instance_id")} if customer else set())
    _attach_tenant_info([customer], instances)
    return CustomerOut(**customer)


@app.put("/api/customers/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    user: dict = Depends(require_user),
    db=Depends(get_db),
):
    row = db.execute(
        """
        SELECT id, name, first_name, last_name, department, vendor, contact_email, instance_id,
               created_at, updated_at
        FROM customers WHERE id = ?
        """,
        (customer_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found.")
    if payload.instance_id:
        instance = db.execute(
            "SELECT id FROM instances WHERE id = ?", (payload.instance_id,)
        ).fetchone()
        if not instance:
            raise HTTPException(status_code=400, detail="Instance does not exist.")
    current = _row_to_dict(row)
    updated_first = (
        payload.first_name if payload.first_name is not None else current["first_name"]
    )
    updated_last = payload.last_name if payload.last_name is not None else current["last_name"]
    updated_name = (
        payload.name
        if payload.name is not None
        else _compose_name(updated_first, updated_last) or current["name"]
    )
    updated = {
        "name": updated_name,
        "first_name": updated_first,
        "last_name": updated_last,
        "department": payload.department
        if payload.department is not None
        else current.get("department"),
        "vendor": payload.vendor if payload.vendor is not None else current["vendor"],
        "contact_email": payload.contact_email
        if payload.contact_email is not None
        else current["contact_email"],
        "instance_id": payload.instance_id
        if payload.instance_id is not None
        else current["instance_id"],
        "updated_at": utc_now(),
    }
    db.execute(
        """
        UPDATE customers
        SET name = ?, first_name = ?, last_name = ?, department = ?, vendor = ?,
            contact_email = ?, instance_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            updated["name"],
            updated["first_name"],
            updated["last_name"],
            updated["department"],
            updated["vendor"],
            updated["contact_email"],
            updated["instance_id"],
            updated["updated_at"],
            customer_id,
        ),
    )
    db.commit()
    row = db.execute(
        """
        SELECT customers.id, customers.name, customers.first_name, customers.last_name,
               customers.department, customers.vendor, customers.contact_email, customers.instance_id,
               customers.created_at, customers.updated_at, instances.name AS instance_name
        FROM customers
        LEFT JOIN instances ON customers.instance_id = instances.id
        WHERE customers.id = ?
        """,
        (customer_id,),
    ).fetchone()
    customer = _row_to_dict(row)
    instances = _load_instances(db, {customer.get("instance_id")} if customer else set())
    _attach_tenant_info([customer], instances)
    return CustomerOut(**customer)


@app.delete("/api/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: str, user: dict = Depends(require_user), db=Depends(get_db)
):
    row = db.execute("SELECT id FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found.")
    db.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


@app.post("/api/onboard", response_model=OnboardResponse, status_code=status.HTTP_201_CREATED)
def onboard_customer(
    payload: OnboardRequest, user: dict = Depends(require_user), db=Depends(get_db)
):
    instance_id = payload.customer.instance_id
    bff_payload = _build_bff_payload(payload.customer)
    if payload.instance:
        instance_id = str(uuid4())
        now = utc_now()
        _notify_bff_onboard(payload.instance.bff_url, bff_payload)
        _update_tenant_subscriber_flags(
            {
                "pg_host": payload.instance.pg_host,
                "pg_port": payload.instance.pg_port,
                "pg_user": payload.instance.pg_user,
                "pg_password": payload.instance.pg_password,
            },
            payload.customer.contact_email,
        )
        db.execute(
            """
            INSERT INTO instances (
                id, name, base_url, status,
                pg_host, pg_port, pg_user, pg_password,
                neo4j_host, neo4j_port, neo4j_user, neo4j_password,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                instance_id,
                payload.instance.name,
                payload.instance.bff_url,
                payload.instance.status,
                payload.instance.pg_host,
                payload.instance.pg_port,
                payload.instance.pg_user,
                payload.instance.pg_password,
                payload.instance.neo4j_host,
                payload.instance.neo4j_port,
                payload.instance.neo4j_user,
                payload.instance.neo4j_password,
                now,
                now,
            ),
        )
    elif instance_id:
        instance = db.execute(
            """
            SELECT id, base_url, pg_host, pg_port, pg_user, pg_password
            FROM instances WHERE id = ?
            """,
            (instance_id,),
        ).fetchone()
        if not instance:
            raise HTTPException(status_code=400, detail="Instance does not exist.")
        instance = _row_to_dict(instance)
        _notify_bff_onboard(instance["base_url"], bff_payload)
        _update_tenant_subscriber_flags(instance, payload.customer.contact_email)
    else:
        raise HTTPException(status_code=400, detail="Instance data is required.")

    full_name = _build_customer_name(payload.customer)
    if not full_name:
        raise HTTPException(
            status_code=400, detail="Customer first name and last name are required."
        )
    customer_id = str(uuid4())
    now = utc_now()
    db.execute(
        """
        INSERT INTO customers (
            id, name, first_name, last_name, department, vendor,
            contact_email, instance_id, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            customer_id,
            full_name,
            payload.customer.first_name,
            payload.customer.last_name,
            payload.customer.department,
            payload.customer.vendor,
            payload.customer.contact_email,
            instance_id,
            now,
            now,
        ),
    )
    db.commit()
    return OnboardResponse(instance_id=instance_id, customer_id=customer_id)
