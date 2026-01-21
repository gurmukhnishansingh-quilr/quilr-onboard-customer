from dataclasses import dataclass, field
import os


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = "Quilr Onboarding"
    database_path: str = os.environ.get("DATABASE_PATH", "backend/app.db")
    cors_origins: list[str] = field(
        default_factory=lambda: _split_csv(os.environ.get("CORS_ORIGINS"))
    )
    session_secret: str = os.environ.get("SESSION_SECRET", "change-me")
    frontend_url: str = os.environ.get("FRONTEND_URL", "http://localhost:3000")

    ms_client_id: str | None = os.environ.get("MS_CLIENT_ID")
    ms_client_secret: str | None = os.environ.get("MS_CLIENT_SECRET")
    ms_tenant_id: str = os.environ.get("MS_TENANT_ID", "common")
    ms_redirect_uri: str = os.environ.get(
        "MS_REDIRECT_URI", "http://localhost:8000/auth/callback"
    )
    auth_required_group_names: list[str] = field(
        default_factory=lambda: _split_csv(os.environ.get("AUTH_REQUIRED_GROUPS"))
        or ["CustomerOnboardAdmin"]
    )
    auth_required_group_ids: list[str] = field(
        default_factory=lambda: _split_csv(os.environ.get("AUTH_REQUIRED_GROUP_IDS"))
    )

    pg_database: str = os.environ.get("PG_DATABASE", "quilr_auth")
    pg_sslmode: str = os.environ.get("PG_SSLMODE", "prefer")
    tenant_table: str = os.environ.get("TENANT_TABLE", "public.tenant")
    tenant_match_column: str = os.environ.get("TENANT_MATCH_COLUMN", "name")
    tenant_name_column: str = os.environ.get("TENANT_NAME_COLUMN", "name")
    tenant_id_column: str = os.environ.get("TENANT_ID_COLUMN", "id")
    tenant_subscriber_column: str = os.environ.get("TENANT_SUBSCRIBER_COLUMN", "subscriberId")
    tenant_cache_ttl_seconds: int = int(
        os.environ.get("TENANT_CACHE_TTL_SECONDS", "900")
    )
    internal_user_cache_ttl_seconds: int = int(
        os.environ.get("INTERNAL_USER_CACHE_TTL_SECONDS", "300")
    )
    connection_timeout_seconds: int = int(
        os.environ.get("CONNECTION_TIMEOUT_SECONDS", "30")
    )
    bff_timeout_seconds: int = int(os.environ.get("BFF_TIMEOUT_SECONDS", "30"))
    bff_verify_ssl: bool = _as_bool(os.environ.get("BFF_VERIFY_SSL", "true"))
    bff_ca_bundle: str | None = os.environ.get("BFF_CA_BUNDLE")
    bff_tls_version: str | None = os.environ.get("BFF_TLS_VERSION")
    default_role_names: list[str] = field(
        default_factory=lambda: _split_csv(os.environ.get("DEFAULT_ROLE_NAMES"))
    )
    default_group_names: list[str] = field(
        default_factory=lambda: _split_csv(os.environ.get("DEFAULT_GROUP_NAMES"))
    )
    user_table: str = os.environ.get("USER_TABLE", "public.user")
    user_tenant_column: str = os.environ.get("USER_TENANT_COLUMN", "tenantId")
    user_tenant_match_mode: str = os.environ.get("USER_TENANT_MATCH_MODE", "eq")
    user_subscriber_column: str = os.environ.get("USER_SUBSCRIBER_COLUMN", "subscriberId")
    user_account_type_column: str = os.environ.get(
        "USER_ACCOUNT_TYPE_COLUMN", "accountType"
    )
    user_account_type_value: str = os.environ.get(
        "USER_ACCOUNT_TYPE_VALUE", "credentials"
    )
    user_account_type_oauth_value: str = os.environ.get(
        "USER_ACCOUNT_TYPE_OAUTH_VALUE", "oauth"
    )
    user_first_name_column: str = os.environ.get("USER_FIRST_NAME_COLUMN", "firstname")
    user_last_name_column: str = os.environ.get("USER_LAST_NAME_COLUMN", "lastname")
    user_username_column: str = os.environ.get("USER_USERNAME_COLUMN", "username")
    user_email_column: str = os.environ.get("USER_EMAIL_COLUMN", "email")
    user_password_column: str = os.environ.get("USER_PASSWORD_COLUMN", "password")
    user_role_ids_column: str = os.environ.get("USER_ROLE_IDS_COLUMN", "roleIds")
    user_group_ids_column: str = os.environ.get("USER_GROUP_IDS_COLUMN", "groupIds")
    user_status_column: str = os.environ.get("USER_STATUS_COLUMN", "status")
    user_verification_column: str = os.environ.get(
        "USER_VERIFICATION_COLUMN", "verification_status"
    )
    user_createdby_column: str = os.environ.get("USER_CREATEDBY_COLUMN", "createdby")
    user_updatedby_column: str = os.environ.get("USER_UPDATEDBY_COLUMN", "updatedby")
    user_email_sent_column: str = os.environ.get("USER_EMAIL_SENT_COLUMN", "emailSent")
    user_id_column: str = os.environ.get("USER_ID_COLUMN", "id")
    role_table: str = os.environ.get("ROLE_TABLE", "public.roles")
    role_id_column: str = os.environ.get("ROLE_ID_COLUMN", "id")
    role_name_column: str = os.environ.get("ROLE_NAME_COLUMN", "name")
    role_tenant_column: str = os.environ.get(
        "ROLE_TENANT_COLUMN", os.environ.get("USER_TENANT_COLUMN", "tenantId")
    )
    role_tenant_match_mode: str = os.environ.get(
        "ROLE_TENANT_MATCH_MODE", os.environ.get("USER_TENANT_MATCH_MODE", "eq")
    )
    role_subscriber_column: str | None = os.environ.get("ROLE_SUBSCRIBER_COLUMN")
    group_table: str = os.environ.get("GROUP_TABLE", "public.group")
    group_id_column: str = os.environ.get("GROUP_ID_COLUMN", "id")
    group_name_column: str = os.environ.get("GROUP_NAME_COLUMN", "name")
    group_tenant_column: str = os.environ.get(
        "GROUP_TENANT_COLUMN", os.environ.get("USER_TENANT_COLUMN", "tenantId")
    )
    group_tenant_match_mode: str = os.environ.get(
        "GROUP_TENANT_MATCH_MODE", os.environ.get("USER_TENANT_MATCH_MODE", "eq")
    )
    group_subscriber_column: str | None = os.environ.get("GROUP_SUBSCRIBER_COLUMN")

    internal_user_default_status: str = os.environ.get(
        "INTERNAL_USER_DEFAULT_STATUS", "active"
    )
    internal_user_default_verification_status: str = os.environ.get(
        "INTERNAL_USER_DEFAULT_VERIFICATION_STATUS", "unverified"
    )
    internal_user_default_createdby: str = os.environ.get(
        "INTERNAL_USER_DEFAULT_CREATEDBY", "OnboardingPortal"
    )
    internal_user_default_updatedby: str = os.environ.get(
        "INTERNAL_USER_DEFAULT_UPDATEDBY", "OnboardingPortal"
    )
    internal_user_default_email_sent: bool = _as_bool(
        os.environ.get("INTERNAL_USER_DEFAULT_EMAIL_SENT", "false")
    )

    dev_auth_bypass: bool = _as_bool(os.environ.get("DEV_AUTH_BYPASS"))
    allow_unverified_tokens: bool = _as_bool(
        os.environ.get("ALLOW_UNVERIFIED_TOKENS", "true")
    )

    @property
    def ms_metadata_url(self) -> str:
        return (
            f"https://login.microsoftonline.com/{self.ms_tenant_id}"
            "/v2.0/.well-known/openid-configuration"
        )


settings = Settings()
